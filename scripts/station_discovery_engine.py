"""Phase 2: discover new station events using declarative official HTML rules.

Station identity comes from a vetted registry, NOT from guessed place names.
A dated event-specific title, a grounded year and article-local station venue
are mandatory. Existing source adapters remain active and are not replaced.
"""
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import fitz
from bs4 import BeautifulSoup
from kyushu_okinawa_events import publication_date
from kanto_remaining_prefectures import event_period as parse_period

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "data" / "station_event_discovery_sources.json"
REPORT = ROOT / "data" / "station_event_discovery_audit.json"
HEADERS = {"User-Agent": "MichinotochuRoadEventBot/2.2 (official station article discovery)"}
EVENT_WORDS = ("イベント", "祭", "まつり", "フェア", "マルシェ", "収穫", "公演",
               "コンサート", "まわし", "宴", "物産展", "体験", "市", "朝市",
               "販売会", "周年", "文化祭", "ツアー", "音楽", "フリマ",
               "マーケット", "花火", "感謝祭", "ライブ", "試食販売", "実演販売", "ワークショップ", "販売")
BLOCK = ("イベントカレンダー", "イベントスケジュール", "月間予定", "募集",
         "応募", "中止", "延期", "休館", "休業", "定休日", "締め切り",
         "締切", "開催しました", "終了しました", "レポート", "振り返り")
DATE_LABEL = re.compile(r"(?:[〖【]?(?:開催日(?:時|程)?|開催期間|イベント日時|日程|日時|開催予定|実施日|日にち)[〗】]?)\s*[:：]?\s*")
VENUE_LABEL = re.compile(r"^(?:[■●◆]\s*)?[〖【]?(?:開催場所|開催会場|会場名|開催地|場所|会場)[〗】]?\s*[:：]?\s*")
ERA = re.compile(r"令和\s*(元|[0-9]{1,2})\s*年")
PUBLICATION_PREFIX = re.compile(r"^(?:20[0-9]{2}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?\s*)+")
DEFAULT_DATE_SELECTORS = ("p", "li", "h2", "h3", "td", "dd")

def clean(text):
    return " ".join(unicodedata.normalize("NFKC", text or "").split())

def _date_text(text):
    def convert(m):
        n = 1 if m.group(1) == "元" else int(m.group(1))
        return str(2018 + n) + "年"
    value = ERA.sub(convert, clean(text))
    # Explicit Japanese "R8 11月10日" notation is year evidence.
    # Do not infer year from a bare 11月10日.
    return re.sub(r"(?<![A-Za-z0-9])R\s*([0-9]{1,2})\s*(?=[0-9]{1,2}月)",
                  lambda m: str(2018 + int(m.group(1))) + "年", value)

def _period(text, posted=None):
    return parse_period(_date_text(text), posted)

def _official_url(url, source, *, article):
    try:
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.username or parsed.password or
                parsed.port is not None or parsed.hostname not in source["allowedHosts"]):
            return False
        if article and not re.fullmatch(source["articlePathPattern"], parsed.path):
            return False
        return True
    except ValueError:
        return False

def _validate_sources(sources):
    ids = set()
    for spec in sources:
        required = ("id", "prefecture", "roadName", "listingUrl",
                    "allowedHosts", "articlePathPattern", "listingLinkSelector",
                    "articleSelector", "titleSelectors", "requiredVenueTokens")
        if any(not spec.get(key) for key in required):
            raise ValueError(f"Incomplete station discovery specification: {spec.get('id')}")
        if spec["id"] in ids:
            raise ValueError(f"Duplicate discovery ID: {spec['id']}")
        ids.add(spec["id"])
        if (not _official_url(spec["listingUrl"], spec, article=False) or
            int(spec.get("maxArticles", 6)) not in range(1, 13)):
            raise ValueError(f"Unsafe discovery source: {spec['id']}")
        re.compile(spec["articlePathPattern"])
        if spec.get("articleMode") in ("verified_official_pdf", "verified_official_event_detail", "verified_official_vendor_schedule"):
            if not _official_url(spec["listingUrl"], spec, article=True):
                raise ValueError(f"Unsafe fixed official event source: {spec['id']}")
            if not spec.get("requiredEventTitle"):
                raise ValueError(f"Missing event title in fixed official source: {spec['id']}")
        if spec.get("articleMode") == "verified_official_pdf":
            if (not spec["listingUrl"].lower().endswith(".pdf")
                    or not _official_url(spec["listingUrl"], spec, article=True)
                    or not spec.get("requiredEventTitle")):
                raise ValueError(f"Unsafe official PDF source: {spec['id']}")

def _links(soup, source):
    """Prefer event-looking links but preserve the listing order within tier."""
    if source.get("articleMode") in ("official_station_program", "dated_station_table", "dated_news_listing", "dated_station_calendar", "verified_official_pdf", "verified_official_event_detail", "verified_official_vendor_schedule"):
        # The official event schedule IS the article; it need not hyperlink
        # back to itself. The parser must still validate each stated date.
        return {source["listingUrl"]: "公式開催案内"}
    found = {}
    for a in soup.select(source["listingLinkSelector"]):
        href = a.get("href", "")
        if not href:
            continue
        url = urljoin(source["listingUrl"], href)
        if not _official_url(url, source, article=True):
            continue
        # Remove fragments, which cannot distinguish two article events.
        parts = urlparse(url)
        url = parts._replace(fragment="").geturl()
        headline = clean(a.get_text(" ", strip=True))
        if len(headline) < 5 or len(headline) > 320:
            continue
        if url not in found:
            found[url] = headline
    preferred = source.get("preferredTitles", [])
    chosen = sorted(found.items(), key=lambda item: (
        not any(w in item[1] for w in preferred) if preferred else False,
        not any(w in item[1] for w in source.get("allowedEventWords", EVENT_WORDS)),
        bool(any(w in item[1] for w in BLOCK)),
    ))
    return dict(chosen)

def _pick_article(soup, spec):
    # CSS "article, main, body" in select_one() would choose <body> first
    # because it appears earlier in document order. Selector *priority* is
    # deliberate: inspect the article before any whole-page fallback.
    for selector in spec["articleSelector"].split(","):
        selector = selector.strip()
        if not selector:
            continue
        node = soup.select_one(selector)
        if node is not None:
            return node
    return soup.select_one("article") or soup.select_one("main")

def _headline(soup, spec, listing_title):
    container = _pick_article(soup, spec)
    terms = spec.get("allowedEventWords") or EVENT_WORDS
    if container is None:
        return ""
    # Website templates sometimes change a post's heading from h1 to h3.
    # Search the configured selectors first, then local headings within this
    # very article. Never take unrelated navigation/other article headings.
    selectors = list(dict.fromkeys([
        *spec["titleSelectors"], "article h1", "main h1", "h1", "h2", "h3", "h4"
    ]))
    for selector in selectors:
        for node in soup.select(selector):
            if node is not container and node not in container.descendants:
                continue
            if node.find_parent(["nav", "aside", "footer"]):
                continue
            txt = clean(node.get_text(" ", strip=True))
            if txt in ("イベント", "イベント情報", "イベント一覧", "お知らせ", "NEWS"):
                continue
            if any(w in txt for w in terms) and not any(w in txt for w in BLOCK):
                return txt
    fallback = clean(listing_title)
    if spec.get("useListingPublicationDate"):
        # A listing card often says "EVENT 2026.10.08 <event name>".
        # This is a *posting* timestamp, never the event date. Keep it
        # available to _listing_posted(), but remove it from the title.
        fallback = re.sub(
            r"^(?:(?:EVENT|NEWS|お知らせ|新着情報)\s+)"
            r"20[0-9]{2}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?\s*",
            "", fallback, flags=re.I
        )
    fallback = PUBLICATION_PREFIX.sub("", fallback)
    return fallback if any(w in fallback for w in terms) and not any(
        w in fallback for w in BLOCK) else ""

def _article_lines(container, spec):
    selectors = spec.get("dateSelectors") or DEFAULT_DATE_SELECTORS
    # A site rule may declare CSS selectors as either a comma-delimited
    # string ("p,tr,td") or a list. Never join individual characters.
    if isinstance(selectors, str):
        selectors = selectors.split(",")
    selectors = [selector.strip() for selector in selectors if selector.strip()]
    nodes = container.select(",".join(selectors))
    if spec.get("splitArticleTextLines"):
        # Labels such as "■開催場所" and their venue can be separate
        # text nodes, rather than paragraph-level HTML elements.
        return [clean(t) for t in container.get_text("\n", strip=True).splitlines()
                if clean(t) and len(clean(t)) <= 250][:200]
    lines = []
    for node in nodes:
        if node.find_parent(["aside", "nav", "footer"]):
            continue
        value = clean(node.get_text(" ", strip=True))
        if value and len(value) <= 250:
            lines.append(value)
    return lines[:140]

def _article_period(title, lines, posted):
    period = _period(title, posted)
    if period:
        return period
    for i, line in enumerate(lines):
        if any(w in line for w in ("応募", "締切", "受付期間", "募集", "投稿", "更新", "過去")):
            continue
        label = DATE_LABEL.search(line[:35])
        if not label:
            continue
        part = line[label.end():]
        if not part and i + 1 < len(lines):
            part = lines[i + 1]
        period = _period(part, posted)
        if period:
            return period
    return None

def _publication(soup, spec, title, today):
    """Prefer an explicitly configured article posting date, not event time."""
    selectors = spec.get("publicationSelector", "")
    for item in soup.select(selectors) if selectors else []:
        value = clean(item.get("content") or item.get("datetime") or item.get_text(" ", strip=True))
        match = re.search(r"(20[0-9]{2})[年./-]([0-9]{1,2})[月./-]([0-9]{1,2})", value)
        if not match:
            continue
        try:
            posted = date(*map(int, match.groups()))
        except ValueError:
            continue
        if posted <= today:
            return posted
    posted = publication_date(soup, title)
    return posted if posted is not None and posted <= today else None


def _listing_posted(listing_title, today):
    """Use only an explicit year/month/day printed beside the official listing."""
    m = re.search(r"20[0-9]{2}[年./-][0-9]{1,2}[月./-][0-9]{1,2}", clean(listing_title))
    if not m:
        return None
    raw = m.group(0)
    parts = re.split(r"[年./-]|月", raw)
    try:
        d = date(*[int(x) for x in parts[:3]])
    except (ValueError, TypeError):
        return None
    return d if d <= today else None


def _article_record(source, soup, listing_title, today, url):
    article = _pick_article(soup, source)
    if article is None:
        return None, "no_article"
    title = _headline(soup, source, listing_title)
    if not title or any(w in title for w in BLOCK):
        return None, "not_event"
    terms = source.get("allowedEventWords") or EVENT_WORDS
    if not any(w in title for w in terms):
        return None, "not_event"
    # One monthly overview commonly contains dozens of independently dated
    # events; never treat its first date as one month-long event.
    if re.search(r"^[0-9]{1,2}月(?:前半|後半)?(?:最新)?イベント情報", clean(title)):
        return None, "multi_event_overview"
    lines = _article_lines(article, source)
    body = clean(article.get_text(" ", strip=True))
    venue_proof = source.get("venueProofPattern", "")
    def on_site(value):
        return (any(w in value for w in source["requiredVenueTokens"]) or
                bool(venue_proof and re.search(venue_proof, value)))
    if not on_site(body):
        return None, "venue_missing"
    has_venue_label = False
    for i, line in enumerate(lines):
        label = VENUE_LABEL.search(line)
        if label:
            has_venue_label = True
            value = line[label.end():] or (lines[i + 1] if i + 1 < len(lines) else "")
            if not on_site(value):
                return None, "offsite"
    if source.get("requireVenueLabel") and not has_venue_label:
        proof = source.get("venueProofPattern", "")
        if not proof or not re.search(proof, body):
            return None, "venue_missing"
    posted = _publication(soup, source, title, today)
    if posted is None and source.get("useListingPublicationDate"):
        posted = _listing_posted(listing_title, today)
    period = _article_period(title, lines, posted)
    if period is None and source.get("allowExplicitDatedParagraph"):
        # An individually titled official event notice may put the date in
        # an unlabeled <p>; do not interpret the posting timestamp as event.
        for line in lines:
            if re.search(r"(?:投稿日|更新日|公開日|掲載日|受付期間|申込期限)", line):
                continue
            dated = _date_text(line)
            if not re.search(r"20[0-9]{2}[年./-][0-9]{1,2}[月./-][0-9]{1,2}", dated):
                continue
            # Publishing metadata (not the event date) must never enter here.
            # A full explicit event year in an event paragraph is admissible.
            event_context = (any(w in line for w in terms) or
                             bool(re.search(r"(?:開催|日時|日程|実施日|イベント)", line)))
            # Some official notices put a full date and time on a bare
            # paragraph, next to a confirmed on-site venue. This is not
            # interchangeable with a bare publication date: require a
            # stated time, a date starting the paragraph, and site proof.
            unlabelled_schedule = (
                bool(re.match(r"^20[0-9]{2}年[0-9]{1,2}月[0-9]{1,2}日", dated))
                and bool(re.search(r"[0-9]{1,2}:[0-9]{2}", dated))
                and (has_venue_label or bool(venue_proof and re.search(venue_proof, body)))
            )
            if not (event_context or unlabelled_schedule):
                continue
            candidate = _period(dated, posted)
            # An article's known publication timestamp must never become
            # the event date just because it appears inside a paragraph.
            if candidate and unlabelled_schedule and not event_context and posted:
                if candidate[0] == posted.isoformat():
                    continue
            if candidate:
                period = candidate
                break
    if period is None:
        return None, "undated"
    if period[1] < today.isoformat():
        return None, "past"
    return {"roadName": source["roadName"], "prefecture": source["prefecture"],
            "title": title, "startDate": period[0], "endDate": period[1],
            "publishedAt": posted.isoformat() if posted else "", "url": url,
            "status": "scheduled"}, "accepted"

SECTION_TITLE = re.compile(r"^[〖【]([^〗】]{3,85})[〗】]$")
SECTION_DATE = re.compile(r"^[🗓📅]?\s*(?:(?:開催日(?:時|程)?|開催期間|日程|日時)\s*[:：]?\s*)?")
SECTION_VENUE = re.compile(r"^[📍]?\s*(?:会場|開催場所)?\s*[:：]?\s*")

def _section_records(spec, soup, today, url):
    """Extract separate titled events from a station's multi-event HTML notice.

    A section needs its own distinctive heading, explicit event date,
    and an on-premises venue line. No global date or whole-month inference.
    """
    article = _pick_article(soup, spec)
    if article is None:
        return [], "no_article"
    body = clean(article.get_text(" ", strip=True))
    # Some official station event roundups never repeat the station name
    # inside the article. In this mode EVERY individual event still needs
    # its own explicitly named, approved on-premises venue (see below).
    if (not spec.get("trustArticleSectionsWithStationVenue") and
            not any(w in body for w in spec["requiredVenueTokens"])):
        return [], "venue_missing"
    heading = _headline(soup, spec, "イベント案内")
    # Some site-specific title selectors are narrower than the article
    # container selected for this roundup (e.g. "article h1" vs <main>).
    # Derive the *actual local heading* for publication_date() so its scope
    # stays within this notice. Never substitute today's year.
    local_heading = article.select_one("h1, h2")
    if local_heading:
        heading = clean(local_heading.get_text(" ", strip=True))
    posted = _publication(soup, spec, heading, today)
    lines = [clean(v) for v in article.get_text("\n", strip=True).splitlines()]
    out = []
    for i, raw in enumerate(lines):
        match = SECTION_TITLE.fullmatch(raw)
        if not match:
            continue
        title = match.group(1).strip()
        if not any(w in title for w in EVENT_WORDS) or any(w in title for w in BLOCK):
            continue
        # The date and location must be part of this one notice section,
        # not the next event or previous station-wide calendar.
        snippet = []
        for line in lines[i + 1:i + 10]:
            if SECTION_TITLE.fullmatch(line):
                break
            snippet.append(line)
        date_found = None
        venue_found = False
        for line in snippet:
            # Official station articles may replace the calendar/pin emoji
            # with explicit labels. Labels are per section, never site-wide.
            explicit_date = (line.startswith(("🗓", "📅")) or
                             bool(re.match(r"^(?:開催日(?:時|程)?|開催期間|日程|日時)\s*[:：]", line)))
            explicit_venue = (line.startswith("📍") or
                              bool(re.match(r"^(?:会場|開催場所|場所)\s*[:：]", line)))
            if explicit_date:
                candidate = _period(SECTION_DATE.sub("", line), posted)
                if candidate:
                    date_found = candidate
            if explicit_venue:
                venue = re.sub(r"^(?:📍\\s*)?(?:会場|開催場所|場所)?\\s*[:：]?\\s*", "", line).strip()
                venue_found = any(token in venue for token in spec["approvedVenueTokens"])
        if not date_found or not venue_found or date_found[1] < today.isoformat():
            continue
        out.append({"roadName": spec["roadName"], "prefecture": spec["prefecture"],
                    "title": title, "startDate": date_found[0], "endDate": date_found[1],
                    "publishedAt": posted.isoformat() if posted else "",
                    "url": url, "status": "scheduled"})
    seen = set()
    unique = []
    for rec in out:
        key = (rec["url"], rec["title"], rec["startDate"], rec["endDate"])
        if key not in seen:
            seen.add(key)
            unique.append(rec)
    return unique, "accepted" if unique else "no_individually_dated_sections"


def _official_program_records(spec, soup, today, url):
    """One official station's program page with explicitly dated event headings.

    A heading followed by its OWN dated line is accepted. The previous or next
    year's page heading, other news, or a bare month may not ground a date.
    """
    container = _pick_article(soup, spec)
    if container is None:
        return [], "no_article"
    text = clean(container.get_text(" ", strip=True))
    if not any(v in text for v in spec["requiredVenueTokens"]):
        return [], "venue_missing"
    lines = [clean(x) for x in container.get_text("\n", strip=True).splitlines() if clean(x)]
    results = []
    for i, line in enumerate(lines):
        for name in spec.get("sectionEventNames", []):
            if name not in line or any(w in line for w in BLOCK):
                continue
            nearby = [line] + lines[i + 1:i + 3]
            # Require the same event's line or immediately following line
            # to carry an EXPLICIT 20xx year. No other publication-year proxy.
            for snippet in nearby:
                if not re.search(r"20[0-9]{2}年[0-9]{1,2}月", snippet):
                    continue
                days = _period(snippet)
                if days and days[1] >= today.isoformat():
                    results.append({"roadName": spec["roadName"], "prefecture": spec["prefecture"],
                                    "title": name, "startDate": days[0], "endDate": days[1],
                                    "publishedAt": "", "url": url, "status": "scheduled"})
                    break
    unique = {(r["title"], r["startDate"], r["endDate"]): r for r in results}
    return list(unique.values()), "accepted" if unique else "no_grounded_program_event"


MONTHLY_HEADING = re.compile(r"(20[0-9]{2})年\s*([0-9]{1,2})月\s*道の駅イベントのご案内")
MONTHLY_DAY = re.compile(r"^([0-9]{1,2})月\s*([0-9]{1,2})日\s*[\(（]([月火水木金土日])")
MONTHLY_OFFSITE = ("道の駅外", "市役所", "ホールで開催", "川の駅で", "町民会館", "別会場")

def _monthly_calendar_records(spec, soup, today, url):
    """Parse individually titled, explicitly day-dated notices on station pages.

    The year and month come from this very article's event-program heading.
    Never make one all-month event or infer missing weekdays from today.
    """
    article = _pick_article(soup, spec)
    if article is None:
        return [], "no_article"
    lines = [clean(x) for x in article.get_text("\n", strip=True).splitlines()]
    heading = next((x for x in lines[:20] if MONTHLY_HEADING.search(x)), "")
    match = MONTHLY_HEADING.search(heading)
    if not match:
        return [], "no_grounded_program_year"
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        return [], "invalid_program_month"
    try:
        grounding = date(year, month, 1)
    except ValueError:
        return [], "invalid_program_month"
    if not any(token in heading for token in ("道の駅イベント",)):
        return [], "venue_missing"
    posted = _publication(soup, spec, heading, today)
    events = []
    for i, line in enumerate(lines):
        dm = MONTHLY_DAY.match(line)
        if not dm or int(dm.group(1)) != month or i == 0:
            continue
        title = lines[i - 1].strip("『』「」 　")
        if not 3 <= len(title) <= 85 or MONTHLY_DAY.match(title):
            continue
        if any(w in title for w in BLOCK):
            continue
        if not any(w in title for w in spec.get("monthlyEventWords", EVENT_WORDS)):
            continue
        period = _period(line, grounding)
        if not period or period[1] < today.isoformat():
            continue
        # The following description must be part of this single event and
        # must not positively identify a different venue.
        segment = []
        for nxt in lines[i+1:i+9]:
            if MONTHLY_DAY.match(nxt):
                break
            segment.append(nxt)
        context = clean(" ".join(segment))
        if any(w in context for w in MONTHLY_OFFSITE):
            continue
        events.append({"roadName":spec["roadName"],"prefecture":spec["prefecture"],
                       "title":title,"startDate":period[0],"endDate":period[1],
                       "publishedAt":posted.isoformat() if posted else "",
                       "url":url,"status":"scheduled"})
    unique = {(x["url"],x["title"],x["startDate"],x["endDate"]):x for x in events}
    return list(unique.values()), "accepted" if unique else "no_individually_dated_monthly_events"


def _dated_station_calendar_records(spec, soup, today, url):
    """Official event calendar: a tightly grouped full-date/title/venue card.

    Unlike article search, this reads only the three *adjacent* fields of an
    individually dated listing. Year, station and event name may not be
    inherited from unrelated cards or site headers.
    """
    container = soup.select_one("main") or soup.select_one("body")
    if container is None:
        return [], "no_article"
    for node in container.select("nav, footer, aside, script, style"):
        node.decompose()
    lines = [clean(x) for x in container.get_text("\n", strip=True).splitlines()
             if clean(x)]
    events = []
    for i, line in enumerate(lines):
        if not re.match(r"^20[0-9]{2}年[0-9]{1,2}月[0-9]{1,2}日", line):
            continue
        if len(line) > 95 or i+2 >= len(lines):
            continue
        title, venue = lines[i+1:i+3]
        if not (5 <= len(title) <= 95
                and any(w in title for w in spec.get("allowedEventWords", EVENT_WORDS))
                and not any(w in title for w in BLOCK)
                and any(t in venue for t in spec["requiredVenueTokens"])):
            continue
        period = _period(line)
        if not period or period[1] < today.isoformat():
            continue
        events.append({"roadName":spec["roadName"],"prefecture":spec["prefecture"],
                       "title":title,"startDate":period[0],"endDate":period[1],
                       "publishedAt":"","url":url,"status":"scheduled"})
    unique={(x["title"],x["startDate"],x["endDate"]):x for x in events}
    return list(unique.values()), "accepted" if unique else "no_strict_official_calendar_cards"


def _dated_news_listing_records(spec, soup, today, url):
    """Official station news where complete notices live on the listing.

    A named event, its immediately following published year, a weekday-
    checked event date, and a nearby explicit station venue are all needed.
    Never take a generic site footer as a venue or the post date as an event.
    """
    container = soup.select_one("main") or soup.select_one("body")
    if container is None:
        return [], "no_article"
    for node in container.select("nav, footer, aside, script, style"):
        node.decompose()
    # Track the actual DOM heading elements instead of comparing text:
    # identical wording in a <p> must never become a second event heading.
    lines = []
    heading_positions = set()
    last_heading = None
    for node in container.find_all(string=True):
        if not str(node).strip():
            continue
        heading = node.find_parent(["h1", "h2", "h3", "h4"])
        if heading is not None:
            if heading is last_heading:
                continue
            value = clean(heading.get_text(" ", strip=True))
        else:
            value = clean(str(node))
        if not value:
            continue
        if heading is not None:
            heading_positions.add(len(lines))
        lines.append(value)
        last_heading = heading
    results = []
    for i, title in enumerate(lines):
        if i not in heading_positions:
            continue
        next_heading = min((pos for pos in heading_positions if pos > i),
                           default=len(lines))
        if not (5 <= len(title) <= 110
                and any(w in title for w in spec.get("allowedEventWords", EVENT_WORDS))
                and not any(w in title for w in BLOCK)
                and re.search(r"[0-9]{1,2}月[0-9]{1,2}日", title)):
            continue
        # The posting year must be immediately next to this announcement.
        local = lines[i+1:min(next_heading, i+4)]
        pub = next((re.fullmatch(r"(20[0-9]{2})[./年-]([0-9]{1,2})[./月-]([0-9]{1,2})日?", x)
                    for x in local if re.fullmatch(
                        r"20[0-9]{2}[./年-][0-9]{1,2}[./月-][0-9]{1,2}日?", x)), None)
        if pub is None:
            continue
        try:
            posted = date(*(int(x) for x in pub.groups()))
        except ValueError:
            continue
        if posted > today:
            continue
        period = _period(title, posted)
        if period is None or period[1] < today.isoformat() or period[0] == posted.isoformat():
            continue
        # A single notice may span multiple paragraphs, but never rely on
        # the site-wide address or another news item's venue.
        local_body = lines[i+1:min(next_heading, i+18)]
        venue = next((j for j, x in enumerate(local_body) if
                      re.match(r"^(?:場所|会場)\s*[:：]?\s*", x) and
                      any(t in x for t in spec["requiredVenueTokens"])), None)
        if venue is None:
            continue
        results.append({"roadName":spec["roadName"],"prefecture":spec["prefecture"],
                        "title":title,"startDate":period[0],"endDate":period[1],
                        "publishedAt":posted.isoformat(),"url":url,"status":"scheduled"})
    unique = {(x["title"], x["startDate"], x["endDate"]): x for x in results}
    return list(unique.values()), "accepted" if unique else "no_strictly_dated_news_notice"


def _dated_station_table_records(spec, soup, today, url):
    """Station-owned event-table rows with per-row year, dates and on-site category.

    The table is the primary official source. We never infer a date from a
    numeric item title (e.g. "1024") or from the surrounding page timestamp.
    """
    host = urlparse(url)
    if host.hostname not in spec["allowedHosts"]:
        return [], "unofficial_listing"
    events = []
    for tr in soup.select("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        if len(cells) < 3:
            continue
        dated = clean(cells[0].get_text(" ", strip=True))
        venue = clean(cells[1].get_text(" ", strip=True))
        if not any(t in venue for t in spec.get("requireCategoryTokens", [])):
            continue
        title = clean(cells[-1].get_text(" ", strip=True))
        if (not any(word in title for word in spec.get("allowedEventWords", EVENT_WORDS))
                or any(w in title for w in BLOCK)):
            continue
        if not re.search(r"20[0-9]{2}年[0-9]{1,2}月", dated):
            continue
        period = _period(dated)
        if not period or period[1] < today.isoformat():
            continue
        # Per-event href if offered, otherwise cite the official dated list.
        a = cells[-1].find("a", href=True)
        page = urljoin(url, a["href"]) if a else url
        if not _official_url(page, spec, article=bool(a)):
            continue
        events.append({"roadName":spec["roadName"],"prefecture":spec["prefecture"],
                       "title":title,"startDate":period[0],"endDate":period[1],
                       "publishedAt":"","url":page,"status":"scheduled"})
    # Some official event lists render three columns as styled divs rather
    # than <tr>. Accept only adjacent date/category/title text rows.
    # The event itself still needs to be named in the source's allow-list.
    if not events:
        lines = [clean(x) for x in soup.get_text("\n", strip=True).splitlines()
                 if clean(x)]
        for i, dated in enumerate(lines):
            if not re.fullmatch(
                    r"20[0-9]{2}年[0-9]{1,2}月[0-9]{1,2}日[～〜~－-]"
                    r"(?:20[0-9]{2}年)?(?:[0-9]{1,2}月)?[0-9]{1,2}日", dated):
                continue
            if i+2 >= len(lines):
                continue
            venue, title = lines[i+1:i+3]
            if (not any(t in venue for t in spec.get("requireCategoryTokens", []))
                    or not any(w in title for w in spec.get("allowedEventWords", EVENT_WORDS))
                    or any(w in title for w in BLOCK)):
                continue
            period = _period(dated)
            if period is None or period[1] < today.isoformat():
                continue
            # Do not invent a detail URL from a listing's surrounding links.
            events.append({"roadName":spec["roadName"],"prefecture":spec["prefecture"],
                           "title":title,"startDate":period[0],"endDate":period[1],
                           "publishedAt":"","url":url,"status":"scheduled"})
    seen={}
    for e in events:
        seen[(e["url"],e["title"],e["startDate"],e["endDate"])]=e
    return list(seen.values()), "accepted" if seen else "no_official_dated_station_rows"


def _verified_official_vendor_schedule_records(spec, soup, today, url):
    """A first-party vendor's dated POP-UP notice at a vetted road station.

    Only the same short schedule section can prove vendor event, station,
    year-specific date and on-site venue; neighbouring stores are off-limits.
    """
    if not _official_url(url, spec, article=True):
        return [], "unofficial_vendor"
    article = _pick_article(soup, spec)
    if article is None:
        return [], "no_article"
    for node in article.select("nav, footer, aside, script, style"):
        node.decompose()
    body = clean(article.get_text(" ", strip=True))
    # Circled sequence numbers become normal digits under NFKC.
    sections = re.split(r"(?=10月の九州の催事[0-9]+)", body)
    key = clean(spec["requiredEventTitle"])
    section = next((part for part in sections if part.startswith(key)), "")
    if not section:
        return [], "vendor_section_missing"
    if any(w in section for w in ("中止", "延期", "終了しました")):
        return [], "vendor_event_cancelled"
    proof = spec.get("venueProofPattern", "")
    if not proof or not re.search(proof, section):
        return [], "vendor_station_missing"
    if not re.search(r"催事場所\s*施設内(?:\s|$)", section):
        return [], "vendor_offsite"
    day = re.search(r"催事日\s*(20[0-9]{2}年[0-9]{1,2}月[0-9]{1,2}日)", section)
    if not day:
        return [], "vendor_date_missing"
    period = _period(day.group(1))
    if not period or period[1] < today.isoformat():
        return [], "vendor_invalid_or_past"
    record = {"roadName":spec["roadName"],"prefecture":spec["prefecture"],
              "title":spec["requiredEventTitle"],
              "startDate":period[0],"endDate":period[1],
              "publishedAt":"","url":url,"status":"scheduled"}
    return [record], "accepted"


def _verified_official_event_detail_records(spec, soup, today, url):
    """One named event on its own official organizer programme detail page.

    Reject a calendar-wide period, date-free announcements and incidental
    station name references: both a dated event period and an explicit
    venue label must be inside the dedicated article.
    """
    if not _official_url(url, spec, article=True):
        return [], "unofficial_detail"
    article = _pick_article(soup, spec)
    if article is None:
        return [], "no_article"
    for bad in article.select("nav, footer, aside, script, style"):
        bad.decompose()
    heading = clean(spec["requiredEventTitle"])
    matches = [clean(n.get_text(" ", strip=True)) for n in
               article.select("h1, h2, h3, h4")]
    if heading not in matches:
        return [], "event_title_missing"
    body = clean(article.get_text(" ", strip=True))
    # "会場 道の駅 湘南ちがさき" belongs to the named exhibition,
    # unlike a generic website's contact/address footer.
    venue_proof = spec.get("venueProofPattern", "")
    if not venue_proof or not re.search(venue_proof, body):
        return [], "event_venue_missing"
    # Event-site programme notation: "2026.10.10 SAT — 11.23 MON"
    # or "2026 10.10 SAT 11.23 MON". The end month/day must be
    # adjacent to the explicitly dated start, not a global page date.
    dated = re.search(r"(?<![0-9])(20[0-9]{2})[.\s/-]+([0-9]{1,2})[./]([0-9]{1,2})(?![0-9])", body)
    if dated is None:
        return [], "event_year_missing"
    nearby = body[dated.end():dated.end()+36]
    second = re.search(r"([0-9]{1,2})[./]([0-9]{1,2})(?![0-9])", nearby)
    if second is None:
        return [], "event_range_missing"
    try:
        yr, m, d = [int(x) for x in dated.groups()]
        start = date(yr, m, d)
        endm, endd = [int(x) for x in second.groups()]
        end = date(yr + (1 if endm < m else 0), endm, endd)
    except ValueError:
        return [], "event_invalid_date"
    if end < start or (end-start).days > 90 or end < today:
        return [], "event_invalid_or_past"
    record = {"roadName":spec["roadName"],"prefecture":spec["prefecture"],
              "title":heading,"startDate":start.isoformat(),
              "endDate":end.isoformat(),"publishedAt":"","url":url,
              "status":"scheduled"}
    return [record], "accepted"


def _verified_official_pdf_records(spec, pdf_text, today, url):
    """Verify one specifically titled station event in an official PDF.

    Do not use a publication date, filename or neighbouring year's headings
    to infer the event year. Each of the official tender document's labelled
    sections must independently support name, calendar date and venue.
    """
    if not _official_url(url, spec, article=True):
        return [], "unofficial_pdf"
    body = clean(pdf_text)
    sections = {}
    for no, label in ((1, "イベント名称"), (2, "開催日時"), (3, "開催場所")):
        pattern = rf"第\s*{no}\s*{label}\s*(.{{0,350}}?)(?=第\s*{no+1}\s*|$)"
        match = re.search(pattern, body)
        if not match:
            return [], f"missing_pdf_section_{no}"
        sections[no] = match.group(1)
    title = clean(spec["requiredEventTitle"])
    if title not in sections[1] or any(w in sections[1] for w in ("中止", "延期")):
        return [], "pdf_event_title_missing"
    venue = sections[3]
    if not any(v in venue for v in spec["requiredVenueTokens"]):
        return [], "pdf_venue_missing"
    if not re.search(r"(?:20[0-9]{2}|令和\s*[0-9]{1,2})\s*年", sections[2]):
        return [], "pdf_explicit_year_missing"
    period = _period(sections[2])
    if not period or period[1] < today.isoformat():
        return [], "pdf_date_invalid_or_past"
    record = {"roadName":spec["roadName"],"prefecture":spec["prefecture"],
              "title":title,"startDate":period[0],"endDate":period[1],
              "publishedAt":"","url":url,"status":"scheduled"}
    return [record], "accepted"


def _fetch_official_pdf_text(url):
    """Download a small, nonredirecting official PDF, then extract embedded text."""
    response = requests.get(url, headers=HEADERS, timeout=(4, 12),
                            allow_redirects=False)
    response.raise_for_status()
    data = response.content
    if response.status_code != 200 or not data.startswith(b"%PDF"):
        raise requests.RequestException("Not a direct official PDF response")
    if len(data) > 8_000_000:
        raise ValueError("Official PDF exceeds size limit")
    try:
        with fitz.open(stream=data, filetype="pdf") as document:
            if len(document) > 12:
                raise ValueError("Official PDF has too many pages")
            return "\n".join(page.get_text("text") for page in document)
    except RuntimeError as exc:
        raise ValueError("Official PDF could not be decoded") from exc


def _fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=(4, 9), allow_redirects=False)
    r.raise_for_status()
    if r.status_code != 200:
        raise requests.RequestException(f"Non-200/redirect status: {r.status_code}")
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return BeautifulSoup(r.text, "html.parser")

def collect_configured_station_events(today, prior=None, sources=None, fetch=None,
                                      report_path=REPORT, pdf_fetch=None,
                                      reconfirm_previous=None):
    """Discover only URLs absent from all current and prior verified records.

    Keeping an already published URL with its known event collector prevents
    inconsistent titles from producing duplicate same-day event records.
    """
    if sources is None:
        registry = json.loads(RULES.read_text(encoding="utf-8"))
        if registry.get("schemaVersion") != 1:
            raise ValueError("Unsupported discovery registry version")
        sources = registry["sources"]
    _validate_sources(sources)
    fetch = fetch or _fetch
    pdf_fetch = pdf_fetch or _fetch_official_pdf_text
    known_urls = {e["url"] for e in (prior or ()) if e.get("url")}
    previous_verified = {(e.get("url"), clean(e.get("title")),
                          e.get("startDate"), e.get("endDate")): e
                         for e in (reconfirm_previous or ())}
    previous_keys = {(e.get("url"), clean(e.get("title")),
                      e.get("startDate"), e.get("endDate"))
                     for e in (prior or ())}
    newly_seen, records, summaries = set(), [], []
    new_count, reconfirmed_count = 0, 0
    reconfirmed_keys = set()
    for spec in sources:
        summary = {"id": spec["id"], "prefecture": spec["prefecture"],
                   "roadName": spec["roadName"], "listingUrl": spec["listingUrl"],
                   "listingError": "", "candidates": 0, "checked": 0,
                   "accepted": 0, "reconfirmed": 0, "knownSkipped": 0,
                   "fetchFailed": 0, "fetchErrors": [],
                   "reasons": {}, "examples": [], "rejectedExamples": []}
        if not spec.get("enabled", False):
            summary["status"] = "disabled"
            summaries.append(summary)
            continue
        try:
            listing = None if spec.get("articleMode") == "verified_official_pdf" else fetch(spec["listingUrl"])
            links = _links(listing, spec)
        except (requests.RequestException, ValueError, AttributeError) as exc:
            summary["listingError"] = f"{type(exc).__name__}: {str(exc)[:140]}"
            summaries.append(summary)
            continue
        summary["candidates"] = len(links)
        for url, text in links.items():
            mode = spec.get("articleMode")
            multi = mode in ("dated_sections", "official_station_program",
                             "monthly_calendar_article", "dated_station_table",
                             "dated_news_listing", "dated_station_calendar",
                             "verified_official_pdf", "verified_official_event_detail",
                             "verified_official_vendor_schedule")
            if not multi and (url in known_urls or url in newly_seen):
                summary["knownSkipped"] += 1
                continue
            if summary["checked"] >= int(spec.get("maxArticles", 6)):
                break
            try:
                detail = (pdf_fetch(url) if mode == "verified_official_pdf" else
                          listing if (mode in ("official_station_program", "dated_station_table", "dated_news_listing", "dated_station_calendar", "verified_official_event_detail", "verified_official_vendor_schedule") and
                                      url == spec["listingUrl"]) else fetch(url))
            except (requests.RequestException, ValueError, AttributeError) as exc:
                summary["fetchFailed"] += 1
                if len(summary["fetchErrors"]) < 3:
                    summary["fetchErrors"].append({
                        "url": url, "type": type(exc).__name__,
                        "detail": str(exc)[:180]})
                continue
            summary["checked"] += 1
            reconfirmed_this_url = 0
            if multi:
                if mode == "official_station_program":
                    found, why = _official_program_records(spec, detail, today, url)
                elif mode == "dated_station_table":
                    found, why = _dated_station_table_records(spec, detail, today, url)
                elif mode == "dated_news_listing":
                    found, why = _dated_news_listing_records(spec, detail, today, url)
                elif mode == "dated_station_calendar":
                    found, why = _dated_station_calendar_records(spec, detail, today, url)
                elif mode == "verified_official_pdf":
                    found, why = _verified_official_pdf_records(spec, detail, today, url)
                elif mode == "verified_official_event_detail":
                    found, why = _verified_official_event_detail_records(spec, detail, today, url)
                elif mode == "verified_official_vendor_schedule":
                    found, why = _verified_official_vendor_schedule_records(spec, detail, today, url)
                elif mode == "monthly_calendar_article":
                    found, why = _monthly_calendar_records(spec, detail, today, url)
                else:
                    found, why = _section_records(spec, detail, today, url)
                # With several events per article, URL-level dedup is unsafe:
                # skip only the exact event instance already in old/current.
                novel = []
                for e in found:
                    key = (e["url"], clean(e["title"]), e["startDate"], e["endDate"])
                    if key in previous_verified:
                        if key not in reconfirmed_keys:
                            # Fresh official evidence matches an existing
                            # event's precise identity and period.
                            records.append(dict(previous_verified[key]))
                            reconfirmed_keys.add(key)
                            summary["reconfirmed"] += 1
                            reconfirmed_this_url += 1
                            reconfirmed_count += 1
                    elif key not in previous_keys:
                        novel.append(e)
                found = novel
            else:
                record, why = _article_record(spec, detail, text, today, url)
                found = [record] if record else []
            if found:
                for record in found:
                    records.append(record)
                    summary["accepted"] += 1
                    new_count += 1
                    if len(summary["examples"]) < 5:
                        summary["examples"].append({"title": record["title"],
                                                    "start": record["startDate"],
                                                    "end": record["endDate"],
                                                    "url": record["url"]})
                newly_seen.add(url)
            elif reconfirmed_this_url == 0:
                summary["reasons"][why] = summary["reasons"].get(why, 0) + 1
                if len(summary["rejectedExamples"]) < 5:
                    summary["rejectedExamples"].append({
                        "title": text[:100], "url": url, "reason": why})
        summaries.append(summary)
        print(f"設定型新規収集 {spec['prefecture']} {spec['roadName']}: "
              f"候補={summary['candidates']} 新規採用={summary['accepted']} "
              f"既存URL={summary['knownSkipped']} 取得失敗={summary['fetchFailed']}")
    audit = {"schemaVersion": 1, "sources": summaries,
             "newEvents": new_count, "reconfirmedEvents": reconfirmed_count}
    if report_path is not None:
        payload = json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
        if not report_path.exists() or report_path.read_text(encoding="utf-8") != payload:
            report_path.write_text(payload, encoding="utf-8")
    return records, audit

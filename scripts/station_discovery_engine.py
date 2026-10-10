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
               "マーケット", "花火", "感謝祭", "ライブ")
BLOCK = ("イベントカレンダー", "イベントスケジュール", "月間予定", "募集",
         "応募", "中止", "延期", "休館", "休業", "定休日", "締め切り",
         "締切", "開催しました", "終了しました", "レポート", "振り返り")
DATE_LABEL = re.compile(r"(?:[〖【]?(?:開催日(?:時|程)?|開催期間|イベント日時|日程|日時|開催予定|実施日|日にち)[〗】]?)\s*[:：]?\s*")
VENUE_LABEL = re.compile(r"^[〖【]?(?:場所|開催場所|会場|開催地|会場名|開催会場)[〗】]?\s*[:：]?\s*")
ERA = re.compile(r"令和\s*(元|[0-9]{1,2})\s*年")
PUBLICATION_PREFIX = re.compile(r"^(?:20[0-9]{2}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?\s*)+")
DEFAULT_DATE_SELECTORS = ("p", "li", "h2", "h3", "td", "dd")

def clean(text):
    return " ".join(unicodedata.normalize("NFKC", text or "").split())

def _date_text(text):
    def convert(m):
        n = 1 if m.group(1) == "元" else int(m.group(1))
        return str(2018 + n) + "年"
    return ERA.sub(convert, clean(text))

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

def _links(soup, source):
    """Prefer event-looking links but preserve the listing order within tier."""
    if source.get("articleMode") == "official_station_program":
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
    chosen = sorted(found.items(), key=lambda item: (
        not any(w in item[1] for w in EVENT_WORDS),
        bool(any(w in item[1] for w in BLOCK)),
    ))
    return dict(chosen)

def _pick_article(soup, spec):
    node = soup.select_one(spec["articleSelector"])
    return node or soup.select_one("article") or soup.select_one("main")

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
    nodes = container.select(",".join(selectors))
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
            if not re.search(r"20[0-9]{2}[年./-][0-9]{1,2}[月./-][0-9]{1,2}", line):
                continue
            period = _period(line, posted)
            if period:
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
SECTION_DATE = re.compile(r"^[🗓📅]?\s*(?:(?:開催日|日時)\s*[:：]?\s*)?")
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
    if not any(w in body for w in spec["requiredVenueTokens"]):
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
            if line.startswith(("🗓", "📅")):
                date_found = _period(SECTION_DATE.sub("", line), posted)
            if line.startswith("📍"):
                venue = SECTION_VENUE.sub("", line).strip()
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


def _fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=(4, 9), allow_redirects=False)
    r.raise_for_status()
    if r.status_code != 200:
        raise requests.RequestException(f"Non-200/redirect status: {r.status_code}")
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return BeautifulSoup(r.text, "html.parser")

def collect_configured_station_events(today, prior=None, sources=None, fetch=None,
                                      report_path=REPORT):
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
    known_urls = {e["url"] for e in (prior or ()) if e.get("url")}
    newly_seen, records, summaries = set(), [], []
    for spec in sources:
        summary = {"id": spec["id"], "prefecture": spec["prefecture"],
                   "roadName": spec["roadName"], "listingUrl": spec["listingUrl"],
                   "listingError": "", "candidates": 0, "checked": 0,
                   "accepted": 0, "knownSkipped": 0, "fetchFailed": 0,
                   "reasons": {}, "examples": []}
        if not spec.get("enabled", False):
            summary["status"] = "disabled"
            summaries.append(summary)
            continue
        try:
            listing = fetch(spec["listingUrl"])
            links = _links(listing, spec)
        except (requests.RequestException, ValueError, AttributeError) as exc:
            summary["listingError"] = f"{type(exc).__name__}: {str(exc)[:140]}"
            summaries.append(summary)
            continue
        summary["candidates"] = len(links)
        for url, text in links.items():
            mode = spec.get("articleMode")
            multi = mode in ("dated_sections", "official_station_program", "monthly_calendar_article")
            if not multi and (url in known_urls or url in newly_seen):
                summary["knownSkipped"] += 1
                continue
            if summary["checked"] >= int(spec.get("maxArticles", 6)):
                break
            try:
                detail = listing if (mode == "official_station_program" and
                                     url == spec["listingUrl"]) else fetch(url)
            except (requests.RequestException, ValueError, AttributeError):
                summary["fetchFailed"] += 1
                continue
            summary["checked"] += 1
            if multi:
                if mode == "official_station_program":
                    found, why = _official_program_records(spec, detail, today, url)
                elif mode == "monthly_calendar_article":
                    found, why = _monthly_calendar_records(spec, detail, today, url)
                else:
                    found, why = _section_records(spec, detail, today, url)
                # With several events per article, URL-level dedup is unsafe:
                # skip only the exact event instance already in old/current.
                known_keys = {(e.get("url"), clean(e.get("title")),
                               e.get("startDate"), e.get("endDate"))
                              for e in (prior or ())}
                found = [e for e in found if (e["url"], clean(e["title"]),
                         e["startDate"], e["endDate"]) not in known_keys]
            else:
                record, why = _article_record(spec, detail, text, today, url)
                found = [record] if record else []
            if found:
                for record in found:
                    records.append(record)
                    summary["accepted"] += 1
                    if len(summary["examples"]) < 5:
                        summary["examples"].append({"title": record["title"],
                                                    "start": record["startDate"],
                                                    "end": record["endDate"],
                                                    "url": record["url"]})
                newly_seen.add(url)
            else:
                summary["reasons"][why] = summary["reasons"].get(why, 0) + 1
        summaries.append(summary)
        print(f"設定型新規収集 {spec['prefecture']} {spec['roadName']}: "
              f"候補={summary['candidates']} 新規採用={summary['accepted']} "
              f"既存URL={summary['knownSkipped']} 取得失敗={summary['fetchFailed']}")
    audit = {"schemaVersion": 1, "sources": summaries, "newEvents": len(records)}
    if report_path is not None:
        payload = json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
        if not report_path.exists() or report_path.read_text(encoding="utf-8") != payload:
            report_path.write_text(payload, encoding="utf-8")
    return records, audit

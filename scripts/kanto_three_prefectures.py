"""Official Kanto event adapters: Ibaraki, Tochigi, Gunma.

A station/venue and event period must be established within the same official
article or heading section. Do not infer the current year from today's date.
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

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data" / "kanto_three_prefectures_audit.json"
SOURCES = {
    "kasama": "https://m-kasama.com/event",
    "ibaraki_prefecture": "https://www.pref.ibaraki.jp/hokenfukushi/shofuku/kikaku/noufuku/documents/r7_nouhukumarusye2.html",
    "mashiko": "https://m-mashiko.com/event/",
    "showa": "https://www.vill.showa.gunma.jp/kurashi/kankou/kankou/event/2018-0718-1005-12.html",
}
HEADERS = {"User-Agent": "MichinotochuRoadEventBot/1.8 (official Kanto events)"}
START = re.compile(r"(?:(20\d{2})年\s*)?(\d{1,2})\s*(?:月|/)\s*(\d{1,2})\s*日?\s*(?:\(([月火水木金土日])(?:[^)]{0,5})\))?")
END = re.compile(r"^\s*(?:[～〜~\-・、]|から|より)\s*(?:(\d{1,2})\s*(?:月|/))?\s*(\d{1,2})\s*日?\s*(?:\(([月火水木金土日])(?:[^)]{0,5})\))?")
PUBLISHED = re.compile(r"(?<!\d)(20\d{2})[./年](\d{1,2})[./月](\d{1,2})日?(?!\d)")
WEEKDAYS = "月火水木金土日"
SKIP = ("中止", "延期", "募集", "休業", "定休日", "参加受付終了")

def clean(value):
    value = " ".join(unicodedata.normalize("NFKC", value or "").split())
    return re.sub(r"令和\s*(\d{1,2})年", lambda m: str(2018 + int(m.group(1))) + "年", value)

def parse_period(value, published=None):
    """Explicit full year or year of the SAME announcement; never today's year."""
    m = START.search(clean(value))
    if not m:
        return None
    year = int(m.group(1)) if m.group(1) else (published.year if published else None)
    if year is None:
        return None
    month, day = int(m.group(2)), int(m.group(3))
    if not m.group(1) and published and published.month >= 11 and month <= 2:
        year += 1
    try:
        first = date(year, month, day)
    except ValueError:
        return None
    if m.group(4) and WEEKDAYS[first.weekday()] != m.group(4):
        return None
    last = first
    follow = END.match(clean(value)[m.end():m.end()+42])
    if follow:
        em = int(follow.group(1)) if follow.group(1) else month
        try:
            last = date(year + (1 if em < month else 0), em, int(follow.group(2)))
        except ValueError:
            return None
        if follow.group(3) and WEEKDAYS[last.weekday()] != follow.group(3):
            return None
    if not 0 <= (last-first).days <= 90:
        return None
    return first.isoformat(), last.isoformat()

def heading_context(heading):
    """Stop at the next heading, never combine different station events."""
    chunks, length = [], 0
    for el in heading.next_elements:
        if getattr(el, "name", None) in ("h1", "h2", "h3", "h4", "h5", "h6"):
            break
        if isinstance(el, str):
            chunks.append(el)
            length += len(el)
            if length > 2100:
                break
    return clean(" ".join(chunks))

def _get(url):
    r = requests.get(url, headers=HEADERS, timeout=17)
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return BeautifulSoup(r.text, "html.parser")

def event_record(pref, station, title, days, source, posted=None):
    return {"roadName": station, "prefecture": pref, "title": clean(title),
            "startDate": days[0], "endDate": days[1],
            "publishedAt": posted.isoformat() if posted else "",
            "url": source, "status": "scheduled"}

def parse_ibaraki_prefecture(soup, today, source=SOURCES["ibaraki_prefecture"]):
    """Government's multi-venue notice: each H3 describes one station."""
    found = []
    for h in soup.select("h2,h3,h4"):
        title = clean(h.get_text(" ", strip=True))
        m = re.search(r"ノウフクマルシェ\s*in\s*道の駅\s*(しもつま|ひたちおおた|かさま)", title, re.I)
        if not m:
            continue
        station, context = m.group(1), heading_context(h)
        match = re.search(r"[【〖]?(?:日時|日\s*時)[】〗]?\s*[:：]?\s*(.{4,95})", context)
        days = parse_period(match.group(1)) if match else None
        if not days or days[1] < today.isoformat():
            continue
        if not re.search(r"[【〖]?(?:場所|場\s*所)[】〗]?\s*[:：]?\s*道の駅\s*" + re.escape(station), context):
            continue
        found.append(event_record("茨城県", station,
                                  "ノウフクマルシェ in 道の駅" + station, days, source))
    return found

def _links(soup, url, hosts, max_count=40):
    links = {}
    for a in soup.select("a[href]"):
        href = urljoin(url, a["href"])
        parsed = urlparse(href)
        if parsed.scheme != "https" or parsed.hostname not in hosts or href.rstrip("/") == url.rstrip("/"):
            continue
        title = clean(a.get_text(" ", strip=True))
        if not title or any(x in title for x in SKIP):
            continue
        card = a.find_parent(["li", "article", "tr"])
        context = clean(card.get_text(" ", strip=True)) if card else title
        links.setdefault(href, (title, context))
        if len(links) >= max_count:
            break
    return links

def parse_kasama_list(soup, today, fetch=_get, source=SOURCES["kasama"]):
    found = []
    links = _links(soup, source, ("m-kasama.com", "www.m-kasama.com"))
    for url, (title, card) in links.items():
        if not re.search(r"\d{1,2}/\d{1,2}", title):
            continue
        if not any(w in title for w in ("フェア", "マーケット", "イベント", "公演", "道の駅de", "マルシェ", "祭", "まつり")):
            continue
        year_match = PUBLISHED.search(card)
        year = int(year_match.group(1)) if year_match else None
        try:
            detail = fetch(url)
        except requests.RequestException:
            continue
        h = detail.select_one("article h1") or detail.select_one("main h1") or detail.select_one("h1")
        article_title = clean(h.get_text(" ", strip=True)) if h else title
        if any(x in article_title for x in SKIP):
            continue
        posted = publication_date(detail, article_title)
        if posted:
            year = posted.year
        # The posting year must be grounded by this article/list card.
        days = parse_period(title, date(year, 1, 1) if year else None)
        if days and days[1] >= today.isoformat():
            display = article_title if "道の駅" in article_title or len(article_title) >= 12 else title
            found.append(event_record("茨城県", "かさま", display, days, url, posted))
    return found, len(links)

def mashiko_event_title(detail, listing_title, url):
    """Choose non-empty article title; empty H1 is common on official pages."""
    candidates = []
    for selector in ('article h1', 'main h1', 'h1', 'meta[property="og:title"]',
                     'meta[name="twitter:title"]'):
        node = detail.select_one(selector)
        if node is not None:
            value = node.get("content", "") if node.name == "meta" else node.get_text(" ", strip=True)
            if value:
                candidates.append(clean(value.split("｜")[0].split(" | ")[0]))
    candidates.append(clean(listing_title))
    if urlparse(url).path.rstrip("/") == "/event/4457":
        candidates.append("道の駅ましこ10周年祭")
    for candidate in candidates:
        candidate = re.sub(r"^(?:20\d{2}[./年]\d{1,2}[./月]\d{1,2}日?\s*)+", "", candidate).strip()
        candidate = re.sub(r"^[〖【]?(?:event|イベント)[〗】]?\s*", "", candidate, flags=re.I).strip()
        candidate = clean(candidate)
        if "10周年祭" in candidate and "ましこ" in clean(detail.get_text(" ", strip=True)):
            return "道の駅ましこ10周年祭"
        if len(candidate) >= 5 and any(w in candidate for w in
                                       ("祭", "イベント", "フェア", "マルシェ", "体験", "収穫")):
            return candidate
    return ""


def parse_mashiko_list(soup, today, fetch=_get, source=SOURCES["mashiko"]):
    found = {}
    links = _links(soup, source, ("m-mashiko.com", "www.m-mashiko.com"))
    # Independently recheck the verified official anniversary detail.
    links.setdefault("https://m-mashiko.com/event/4457/", ("道の駅ましこ10周年祭", ""))
    for url, (title, context) in links.items():
        if not re.search(r"/event/\d+/?$", urlparse(url).path):
            continue
        try:
            detail = fetch(url)
        except requests.RequestException:
            continue
        article_title = mashiko_event_title(detail, title, url)
        if not article_title or any(x in article_title for x in SKIP):
            continue
        article = detail.select_one("main") or detail.select_one("article") or detail
        body = clean(article.get_text(" ", strip=True))
        dm = re.search(r"(?:[【〖]?開催日[】〗]?|開催日時)\s*[:：]?\s*((?:20\d{2}年|令和\d+年)\s*\d{1,2}月\d{1,2}日(?:\([^)]{1,6}\))?)", body)
        days = parse_period(dm.group(1)) if dm else None
        if not days or days[1] < today.isoformat():
            continue
        if "道の駅ましこ" not in clean(detail.get_text(" ", strip=True)):
            continue
        record = event_record("栃木県", "ましこ", article_title, days, url)
        key = (record["roadName"], record["startDate"], record["endDate"], record["title"])
        prev = found.get(key)
        # For the anniversary event, use its explicitly verified detail URL
        # instead of a second listing entry describing the same ceremony.
        if prev is None or urlparse(url).path.rstrip("/") == "/event/4457":
            found[key] = record
    return list(found.values()), len(links)

def parse_showa_calendar(soup, today, source=SOURCES["showa"]):
    found = []
    for h in soup.select("h3,h4,h5,h6"):
        title = clean(h.get_text(" ", strip=True))
        if not title.startswith("道の駅・") or any(x in title for x in SKIP):
            continue
        context = heading_context(h)
        m = re.search(r"[【〖]?(?:日時|日\s*時)[】〗]?\s*[:：]?\s*((?:令和\s*\d+年|20\d{2}年).{5,60})", context)
        days = parse_period(m.group(1)) if m else None
        if not days or days[1] < today.isoformat():
            continue
        if not re.search(r"[【〖]?(?:場所|場\s*所)[】〗]?\s*[:：]?\s*道の駅\s*あぐりーむ昭和", context):
            continue
        found.append(event_record("群馬県", "あぐりーむ昭和",
                                  title.replace("道の駅・", "", 1).strip(), days, source))
    return found

def collect_three_kanto_prefectures(today):
    entries, reports = [], []
    adapters = (("茨城県", "ibaraki_prefecture", parse_ibaraki_prefecture),
                ("茨城県", "kasama", parse_kasama_list),
                ("栃木県", "mashiko", parse_mashiko_list),
                ("群馬県", "showa", parse_showa_calendar))
    for pref, key, parser in adapters:
        url = SOURCES[key]
        item = {"prefecture": pref, "source": url, "status": "",
                "candidates": 0, "accepted": 0, "examples": [], "error": ""}
        try:
            value = parser(_get(url), today)
            if isinstance(value, tuple):
                records, item["candidates"] = value
            else:
                records = value
                item["candidates"] = len(records)
            item["accepted"] = len(records)
            item["examples"] = [{"roadName": e["roadName"], "title": e["title"],
                                 "startDate": e["startDate"], "endDate": e["endDate"]}
                                for e in records[:8]]
            entries.extend(records)
            item["status"] = "checked"
        except requests.RequestException as exc:
            item["status"] = "fetch_failed"
            item["error"] = f"{type(exc).__name__}: {str(exc)[:150]}"
        except Exception as exc:
            item["status"] = "parse_failed"
            item["error"] = f"{type(exc).__name__}: {str(exc)[:150]}"
        reports.append(item)
        print(f"関東3県 {pref} {key}: {item['status']} / 候補 {item['candidates']} / 採用 {item['accepted']}")
    unique = {(x["prefecture"], x["roadName"], x["url"], x["startDate"], x["endDate"]): x
              for x in entries}
    audit = {"schemaVersion": 1, "sources": reports, "accepted": len(unique)}
    payload = json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
    if not AUDIT.exists() or AUDIT.read_text(encoding="utf-8") != payload:
        AUDIT.write_text(payload, encoding="utf-8")
    return list(unique.values())

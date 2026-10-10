"""Hokuriku official event-calendar collector: station + explicit date range."""
import re
import json
from pathlib import Path
from datetime import date, timedelta
from urllib.parse import urljoin, urlparse, parse_qs
import requests
from bs4 import BeautifulSoup

BASE = "https://www.hokuriku-michinoeki.jp"
CALENDAR = BASE + "/contents/event/"
STATIONS = {"親不知ピアパーク": "新潟県", "うみてらす名立": "新潟県",
            "氷見": "富山県", "めぐみ白山": "石川県",
            "しらやまさん": "石川県"}
DATES = r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日"
EVENT_ENTRY = re.compile(r"(?P<station>" + "|".join(map(re.escape, sorted(STATIONS,key=len,reverse=True))) +
    r")\s*" + DATES + r"\s*" + DATES + r"(?P<title>.{4,140})")
HEADERS = {"User-Agent": "MichinotochuRoadEventBot/1.5 (Hokuriku official events)"}

def extract_hokuriku(text, today, source):
    """Parse individual event cards, never infer dates from page-level calendar."""
    normalized = " ".join(text.split())
    match = EVENT_ENTRY.search(normalized)
    if not match:
        return None
    station = match.group("station")
    d = match.groups()[1:7]
    try:
        first = date(*map(int, d[:3]))
        last = date(*map(int, d[3:]))
    except ValueError:
        return None
    if first > last or last < today or (last-first).days > 366:
        return None
    title = match.group("title").strip(" ・　")
    # Exclude calendar boilerplate and records without a recognisable event.
    if not title or "登録されたイベントはありません" in title:
        return None
    return {"roadName": station, "prefecture": STATIONS[station], "title": title,
            "startDate": first.isoformat(), "endDate": last.isoformat(),
            "publishedAt": "", "url": source, "status": "scheduled"}

def extract_hokuriku_cards(soup, today, page_url):
    """Read event-specific links and their surrounding card, not only link text.

    On the official calendar, station name and two dates can be sibling
    elements beside the article link. A full-page scan would mix events.
    """
    records = {}
    diagnostics = {"articleLinks": 0, "matchedCards": 0, "unmatchedArticleLinks": 0}
    for anchor in soup.select("a[href]"):
        href = urljoin(page_url, anchor.get("href", ""))
        parsed = urlparse(href)
        if parsed.hostname not in ("www.hokuriku-michinoeki.jp", "hokuriku-michinoeki.jp"):
            continue
        article_link = parsed.path.rstrip("/") == "/contents/event" and bool(parse_qs(parsed.query).get("article"))
        # Calendar cards sometimes link a different official detail URL.
        link_text = anchor.get_text(" ", strip=True)
        views = [anchor]
        parent = anchor.parent
        for _ in range(4):
            if parent is None or parent.name in ("body", "html"):
                break
            views.append(parent)
            parent = parent.parent
        item = None
        for node in views:
            node_text = node.get_text(" ", strip=True)
            if not 10 <= len(node_text) <= 650:
                continue
            # Require an exact station plus two explicit dates in the same
            # limited card. Never use a date found in a different event card.
            entry = extract_hokuriku(node_text, today, href)
            if entry:
                item = entry
                break
        if article_link:
            diagnostics["articleLinks"] += 1
        if not item:
            if article_link:
                diagnostics["unmatchedArticleLinks"] += 1
            continue
        # Only publish a linked official detail page, not calendar-navigation
        # links that happen to be inside an event-card container.
        if not article_link:
            continue
        if link_text and 4 <= len(link_text) <= 100 and not re.search(DATES, link_text):
            if not any(skip in link_text for skip in ("前月", "翌月", "前週", "翌週", "詳細", "もっと見る")):
                item["title"] = link_text
        key = (item["roadName"], item["url"], item["startDate"])
        records[key] = item
        diagnostics["matchedCards"] += 1
    return list(records.values()), diagnostics


AUDIT_FILE = Path(__file__).resolve().parents[1] / "data" / "hokuriku_event_audit.json"

def save_hokuriku_audit(pages, total):
    audit = {"schemaVersion": 1, "pages": pages, "accepted": total}
    content = json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
    if not AUDIT_FILE.exists() or AUDIT_FILE.read_text(encoding="utf-8") != content:
        AUDIT_FILE.write_text(content, encoding="utf-8")

def collect_hokuriku(today):
    # A week-based official calendar; request overlapping weeks to capture
    # ongoing and upcoming events, with a bounded number of network calls.
    found = {}
    audits = []
    for offset in (0, 7, 14, 21, 28, 35):
        day = today + timedelta(days=offset)
        url = CALENDAR + "?dc=" + day.isoformat()
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"北陸カレンダー取得失敗 {url}: {exc}")
            audits.append({"date": day.isoformat(), "url": url, "error": str(exc)[:180]})
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        records, stats = extract_hokuriku_cards(soup, today, response.url)
        links = [urljoin(response.url, a.get("href", "")) for a in soup.select("a[href]")]
        event_links = [href for href in links if "/contents/event" in urlparse(href).path]
        page_text = soup.get_text(" ", strip=True)
        audits.append({
            "date": day.isoformat(), "url": response.url,
            "htmlSize": len(response.content), "links": len(links),
            "eventLinks": len(event_links),
            "sampleEventLinks": event_links[:5],
            "stationsInPage": [station for station in STATIONS if station in page_text],
            "articleLinks": stats["articleLinks"],
            "matchedCards": stats["matchedCards"],
            "unmatchedArticleLinks": stats["unmatchedArticleLinks"],
            "sampleText": page_text[:220]
        })
        for item in records:
            found[(item["roadName"], item["url"], item["startDate"])] = item
        print(f"北陸公式 {day.isoformat()}: 詳細リンク {stats['articleLinks']} / "
              f"駅・期間照合 {len(records)} / 未照合 {stats['unmatchedArticleLinks']}")
        if not records:
            print(f"北陸公式・サンプル: {soup.get_text(' ', strip=True)[:220]}")
    save_hokuriku_audit(audits, len(found))
    return list(found.values())

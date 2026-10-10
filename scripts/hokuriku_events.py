"""Hokuriku official event-calendar collector: station + explicit date range."""
import re
from datetime import date, timedelta
from urllib.parse import urljoin, urlparse
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

def collect_hokuriku(today):
    # A week-based official calendar; request overlapping weeks to capture
    # ongoing and upcoming events, with a bounded number of network calls.
    found = {}
    for offset in (0, 7, 14, 21, 28, 35):
        day = today + timedelta(days=offset)
        url = CALENDAR + "?dc=" + day.isoformat()
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"北陸カレンダー取得失敗 {url}: {exc}")
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        candidates = 0
        for anchor in soup.select("a[href]"):
            href = urljoin(response.url, anchor["href"])
            host = urlparse(href).hostname or ""
            if host not in ("www.hokuriku-michinoeki.jp", "hokuriku-michinoeki.jp"):
                continue
            text = anchor.get_text(" ", strip=True)
            item = extract_hokuriku(text, today, href)
            if item:
                found[(item["roadName"],item["title"],item["startDate"])] = item
                candidates += 1
        print(f"北陸公式 {day.isoformat()}: 駅と期間を確認={candidates}")
    return list(found.values())

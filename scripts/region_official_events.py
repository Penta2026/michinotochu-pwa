"""Official roadside station site collectors, starting with Tohoku.

Do not infer an event end date from publication time or unrelated contests.
Sources are station-managed websites; each handler can be expanded independently.
"""
import re
from datetime import date
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

APPLE_HILL = "https://www.applehill.co.jp/"
USER_AGENT = {"User-Agent": "MichinotochuRoadEventBot/1.1 (official public notices; daily)"}

def _clean(value):
    return re.sub(r"\s+", " ", value or "").strip()

def _date(year, month, day):
    return date(int(year), int(month), int(day)).isoformat()

def _apple_hill_period(text):
    # Date is explicitly introduced with 日時, not taken from unrelated
    # contest submissions or the publication timestamp.
    match = re.search(r"日時\s*[:：]\s*(?:令和\s*(\d+)\s*年|(20\d{2})\s*年)\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if not match:
        return None
    year = (2018 + int(match.group(1))) if match.group(1) else int(match.group(2))
    month = int(match.group(3))
    day = int(match.group(4))
    try:
        start = date(year, month, day)
    except ValueError:
        return None
    rest = text[match.end():match.end()+55]
    # For "10月17日(土)・18日(日)" find the second day; for a full
    # "10月17日〜11月2日" range use the next explicit month.
    end = start
    second = re.search(r"\s*[・〜～\-]\s*(?:(\d{1,2})\s*月\s*)?(\d{1,2})\s*日", re.sub(r"\([^)]*\)", "", rest))
    if second:
        try:
            em = int(second.group(1)) if second.group(1) else month
            ey = year + (1 if em < month else 0)
            end = date(ey, em, int(second.group(2)))
        except ValueError:
            return None
    if end < start or (end - start).days > 100:
        return None
    return start.isoformat(), end.isoformat()

def collect_tohoku(today=None):
    today = today or date.today()
    home = requests.get(APPLE_HILL, timeout=18, headers=USER_AGENT)
    home.raise_for_status()
    soup = BeautifulSoup(home.text, "html.parser")
    candidates = []
    for link in soup.select('a[href*="infodetail"]'):
        # Get title from link itself, heading or nearby text.
        card = link.find_parent(["article", "li", "div"]) or link.parent
        context = _clean(card.get_text(" ", strip=True)) if card else ""
        title = _clean(link.get_text(" ", strip=True))
        if not title or title == "詳細はこちら！":
            title = context
        if not any(word in title for word in ("祭", "イベント", "フェスタ", "マルシェ")):
            continue
        href = urljoin(APPLE_HILL, link.get("href", ""))
        if urlparse(href).hostname != "www.applehill.co.jp":
            continue
        if href not in candidates:
            candidates.append(href)
    events = []
    for href in candidates[:12]:
        page = requests.get(href, timeout=18, headers=USER_AGENT)
        page.raise_for_status()
        detail = BeautifulSoup(page.text, "html.parser")
        heading = detail.find(["h1","h2","h3"])
        heading_text = _clean(heading.get_text(" ",strip=True)) if heading else ""
        content = _clean(detail.get_text(" ",strip=True))
        if "アップルヒル秋の大収穫祭" not in content and "アップルヒル 秋の大収穫祭" not in content:
            continue
        period = _apple_hill_period(content)
        if not period or period[1] < today.isoformat():
            continue
        events.append({"roadName":"なみおか","prefecture":"青森県",
            "title":"アップルヒル秋の大収穫祭",
            "startDate":period[0],"endDate":period[1],
            "publishedAt":"","url":href,"status":"scheduled"})
    print(f"東北・道の駅なみおか: 告知候補 {len(candidates)} / 採用 {len(events)}")
    return events

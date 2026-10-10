"""Hokkaido official station news collector.

Station identity comes from the official site's station-specific URL category,
not from unrelated station links on the page. Event dates must be explicit in
the notice title or event-labelled detail paragraphs.
"""
import re
import unicodedata
from datetime import date
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HOME = "https://hokkaido-michinoeki.jp/"
HEADERS = {"User-Agent": "MichinotochuRoadEventBot/1.4 (official event notices; daily)"}
STATIONS = {
    "shiranukainfo": "しらぬか恋問",
    "makkariinfo": "真狩フラワーセンター",
    "horokanaiinfo": "森と湖の里ほろかない",
    "nanaeinfo": "なないろ・ななえ",
    "hidakajukaiinfo": "樹海ロード日高",
    "takikawainfo": "たきかわ",
    "shibetsuinfo": "羊のまち 侍・しべつ",
}
EVENT_TERMS = ("祭", "まつり", "マルシェ", "フェス", "物産展", "イベント", "収穫", "フェア", "コンサート", "ライブ", "催し")
BLOCK = ("中止", "延期", "休館", "休業", "営業時間", "募集")
DATE = re.compile(r"(20[0-9]{2})年\s*([0-9]{1,2})月\s*([0-9]{1,2})日")
SHORT = re.compile(r"(?<![0-9])([0-9]{1,2})月\s*([0-9]{1,2})日")
DAY_END = re.compile(r"^[\s()月火水木金土日祝・]*[～〜~－–-]\s*(?:([0-9]{1,2})月\s*)?([0-9]{1,2})日")
SECOND_DAY = re.compile(r"^[\s()月火水木金土日祝・]*[・、]\s*(?:([0-9]{1,2})月\s*)?([0-9]{1,2})日")
LABEL = re.compile(r"(?:開催日(?:時|程)?|開催期間|イベント日時|日時|日程)\s*[：:]?\s*(.{4,100})")

def normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text or "").split())

def parse_dates(text, today, *, allow_short=False):
    value = normalize(text)
    full = DATE.search(value)
    short = SHORT.search(value) if allow_short else None
    if full:
        y, month, day = map(int, full.groups())
        end_of_first = full.end()
    elif short:
        month, day = map(int, short.groups())
        # Month/day without year must agree with current season.
        y = today.year
        if today.month >= 11 and month <= 2:
            y += 1
        end_of_first = short.end()
    else:
        return None
    try:
        first = date(y, month, day)
    except ValueError:
        return None
    tail = value[end_of_first:end_of_first + 38]
    match = DAY_END.match(tail) or SECOND_DAY.match(tail)
    last = first
    if match:
        em = int(match.group(1)) if match.group(1) else month
        ey = y + (1 if em < month else 0)
        try:
            last = date(ey, em, int(match.group(2)))
        except ValueError:
            return None
    if not 0 <= (last - first).days <= 90 or last < today:
        return None
    if not full and (first - today).days > 120:
        return None
    return first.isoformat(), last.isoformat()

def collect_hokkaido(today):
    session = requests.Session()
    response = session.get(HOME, headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    candidates = {}
    for a in soup.select('a[href*="/michiekiinfo/"]'):
        url = urljoin(HOME, a["href"])
        parsed = urlparse(url)
        if parsed.hostname not in ("hokkaido-michinoeki.jp", "www.hokkaido-michinoeki.jp"):
            continue
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 3 or parts[0] != "michiekiinfo" or parts[1] not in STATIONS:
            continue
        title = normalize(a.get_text(" ", strip=True))
        if not any(w in title for w in EVENT_TERMS) or any(w in title for w in BLOCK):
            continue
        candidates.setdefault(url, (title, STATIONS[parts[1]]))
        if len(candidates) >= 35:
            break
    stats = {"accepted": 0, "no_date": 0, "past": 0, "failed": 0}
    output = []
    for url, (title, road) in candidates.items():
        try:
            r = session.get(url, headers=HEADERS, timeout=12)
            r.raise_for_status()
            detail = BeautifulSoup(r.text, "html.parser")
        except requests.RequestException as exc:
            stats["failed"] += 1
            print(f"北海道詳細取得失敗: {url} {exc}")
            continue
        # Prefer date in event title, then *labelled* date inside article.
        dates = parse_dates(title, today, allow_short=False)
        if dates is None:
            article = detail.select_one("article") or detail.select_one("main")
            if article:
                for node in article.select("p, li, td, dd, h2, h3"):
                    value = normalize(node.get_text(" ", strip=True))
                    if len(value) > 350:
                        continue
                    m = LABEL.search(value)
                    if m:
                        dates = parse_dates(m.group(1), today, allow_short=True)
                        if dates:
                            break
        if dates is None:
            # A year-less month/day title can be used only if the official
            # article has an explicit matching publication year.
            date_meta = detail.select_one('meta[property="article:published_time"], time[datetime]')
            stamp = (date_meta.get("content") or date_meta.get("datetime") or "") if date_meta else ""
            year_match = re.match(r"(20[0-9]{2})", stamp)
            if year_match and int(year_match.group(1)) == today.year:
                dates = parse_dates(title, today, allow_short=True)
        if dates is None:
            # Some station notices put a short date next to the event name
            # without a "開催日" label. Require explicit publication year and
            # a short, event-specific text node; never scan the entire page.
            date_meta = detail.select_one('meta[property="article:published_time"], time[datetime]')
            stamp = (date_meta.get("content") or date_meta.get("datetime") or "") if date_meta else ""
            valid_year = re.match(r"(20[0-9]{2})", stamp)
            article = detail.select_one("article") or detail.select_one("main")
            if valid_year and int(valid_year.group(1)) == today.year and article:
                for node in article.select("p, li, h2, h3"):
                    value = normalize(node.get_text(" ", strip=True))
                    if len(value) > 180 or not any(w in value for w in EVENT_TERMS):
                        continue
                    if any(w in value for w in ("投稿日", "更新日", "過去", "終了", "中止")):
                        continue
                    if not SHORT.search(value):
                        continue
                    dates = parse_dates(value, today, allow_short=True)
                    if dates:
                        print(f"北海道・本文から日付確定: {road} / {value[:75]}")
                        break
        if dates is None:
            stats["no_date"] += 1
            print(f"北海道・日付未確定: {road} / {title}")
            continue
        output.append({"roadName": road, "prefecture": "北海道", "title": title,
                       "startDate": dates[0], "endDate": dates[1],
                       "publishedAt": "", "url": url, "status": "scheduled"})
        stats["accepted"] += 1
    print(f"北海道公式: 告知候補 {len(candidates)} / 採用 {stats['accepted']} / "
          f"日付未確定 {stats['no_date']} / 取得失敗 {stats['failed']}")
    return output

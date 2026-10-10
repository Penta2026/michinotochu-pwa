"""Six-prefecture Kyushu station event coverage.

Station names and prefectures are tied to vetted official source URLs.
A notice is published only with an explicit event date; publication dates,
nearby attraction dates and event recruitment deadlines are not event dates.
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

SOURCES = (
    {"prefecture": "佐賀県", "road": "しろいし", "list": "https://www.michinoeki-shiroishi.jp/news/",
     "hosts": ("www.michinoeki-shiroishi.jp",)},
    {"prefecture": "長崎県", "road": "させぼっくす９９", "list": "https://sasebox99.com/",
     "hosts": ("sasebox99.com", "www.sasebox99.com")},
    {"prefecture": "熊本県", "road": "すいかの里植木", "list": "https://suikanosato-ueki.com/category/event_info/",
     "hosts": ("suikanosato-ueki.com", "www.suikanosato-ueki.com")},
    {"prefecture": "大分県", "road": "耶馬トピア", "list": "https://www.visit-oita.jp/events/",
     "hosts": ("www.visit-oita.jp", "visit-oita.jp"),
     "venue": "道の駅耶馬トピア",
     "seed": ("https://www.city-nakatsu.jp/doc/2026100500057/",)},
    {"prefecture": "宮崎県", "road": "都城NiQLL", "list": "https://coconiqll.co.jp/info/",
     "hosts": ("coconiqll.co.jp", "www.coconiqll.co.jp")},
    {"prefecture": "鹿児島県", "road": "たるみずはまびら",
     "list": "https://tarumizuhamabira.jp/information/",
     "hosts": ("tarumizuhamabira.jp", "www.tarumizuhamabira.jp")},
)
REPORT = Path(__file__).resolve().parents[1] / "data" / "kyushu_six_prefectures_audit.json"
HEADERS = {"User-Agent": "MichinotochuRoadEventBot/1.7 (six station official notices; daily)"}
EVENT_WORDS = ("祭", "まつり", "感謝", "フェス", "フェア", "イベント",
               "マルシェ", "夜市", "灯籠", "コンサート", "体験", "朝市", "開催", "講座")
EXCLUDE = ("中止", "延期", "求人", "定休日", "休業", "営業時間", "休館",
           "出店募集", "参加者募集", "申込締切", "公募", "通行止め", "お詫び")
DATE = re.compile(
    r"(?:(20\d{2})年\s*)?(\d{1,2})月\s*(\d{1,2})日"
    r"(?:\s*[\(（]([月火水木金土日])[^)）]{0,6}[\)）])?"
)
WEEKDAY = "月火水木金土日"
SHORT_END = re.compile(
    r"^\s*(?:月曜日|火曜日|水曜日|木曜日|金曜日|土曜日|日曜日)?\s*"
    r"(?:[～〜~\-－–]|から|より)\s*(?:(\d{1,2})月)?\s*(\d{1,2})日"
)
LABEL = re.compile(r"(?:開催日時|開催期間|開催日|開催予定日|実施期間|イベント日時|日時|日程|期間)\s*[:：]?\s*")
TITLE_EVENT_DATE = re.compile(r"\d{1,2}月\d{1,2}日")
MAX_CANDIDATES = 15

def clean(value):
    txt = unicodedata.normalize("NFKC", value or "")
    txt = re.sub(r"令和\s*(\d{1,2})年", lambda m: str(2018 + int(m.group(1))) + "年", txt)
    txt = re.sub(r"\bR\s*(\d{1,2})\s*(?=\d{1,2}月)", lambda m:
                 str(2018 + int(m.group(1))) + "年", txt)
    return " ".join(txt.split())

def parsed_date(year, month, day):
    try:
        return date(int(year), int(month), int(day))
    except (ValueError, TypeError):
        return None

def explicit_event_period(fragment, published=None):
    """One start date and at most one nearby end date; reject unknown starts."""
    value = clean(fragment)
    if LABEL.match(value):
        value = LABEL.sub("", value, count=1)
    if re.match(r"^[～〜~\-－–]", value):
        return None
    dates = list(DATE.finditer(value))
    if not dates or len(dates) > 2:
        return None
    first_match = dates[0]
    if first_match.group(1):
        year = int(first_match.group(1))
    elif published:
        year = published.year
        if published.month >= 11 and int(first_match.group(2)) <= 2:
            year += 1
    else:
        return None
    first = parsed_date(year, first_match.group(2), first_match.group(3))
    if not first or (first_match.group(4) and WEEKDAY[first.weekday()] != first_match.group(4)):
        return None
    last = first
    if len(dates) == 2:
        between = value[dates[0].end():dates[1].start()]
        if len(between) > 16 or not re.search(r"[～〜~\-－–]|から|より", between):
            return None
        end_match = dates[1]
        end_year = int(end_match.group(1)) if end_match.group(1) else first.year
        end_month = int(end_match.group(2))
        if not end_match.group(1) and end_month < first.month:
            end_year += 1
        last = parsed_date(end_year, end_month, end_match.group(3))
        if not last or (end_match.group(4) and WEEKDAY[last.weekday()] != end_match.group(4)):
            return None
    else:
        tail = value[dates[0].end():]
        end_match = SHORT_END.match(tail)
        if end_match:
            end_month = int(end_match.group(1)) if end_match.group(1) else first.month
            end_year = first.year + (1 if end_month < first.month else 0)
            last = parsed_date(end_year, end_month, end_match.group(2))
    if not last or last < first or (last - first).days > 120:
        return None
    return first.isoformat(), last.isoformat()

def event_date_from_official_article(title, soup, published=None):
    """Dates from an event-specific title or labelled event date text only."""
    title = clean(title)
    p = explicit_event_period(title, published)
    if p:
        return p
    area = (soup.select_one(".entry-content") or soup.select_one(".post-content")
            or soup.select_one("article") or soup.select_one("main") or soup.body)
    if area is None:
        return None
    for node in area.select("p, li, td, dd, h2, h3, div, section"):
        raw = clean(node.get_text(" ", strip=True))
        if len(raw) > 240 or not LABEL.search(raw[:35]):
            continue
        m = LABEL.search(raw)
        # Don't use dates before a label: these often are publication dates.
        if m and m.start() <= 15:
            p = explicit_event_period(raw[m.end():m.end()+105], published)
            if p:
                return p
    # A labelled date split among text and span/br nodes is still a single
    # article. Keep a small window starting at the first explicit label.
    body = clean(area.get_text(" ", strip=True))
    for match in LABEL.finditer(body):
        snippet = body[match.end():match.end()+90]
        p = explicit_event_period(snippet, published)
        if p:
            return p
    return None

def _candidate_links(spec, soup, base_url):
    """Follow only same-host event article links, never non-station places."""
    options = {}
    for anchor in soup.select("a[href]"):
        title = clean(anchor.get_text(" ", strip=True))
        if not 7 <= len(title) <= 150 or not any(word in title for word in EVENT_WORDS):
            continue
        if any(word in title for word in EXCLUDE):
            continue
        link = urljoin(base_url, anchor.get("href", ""))
        parts = urlparse(link)
        if parts.scheme != "https" or parts.hostname not in spec["hosts"]:
            continue
        if link.rstrip("/") == base_url.rstrip("/") or any(
            p in parts.path for p in ("/category/", "/tag/", "/page/", "/feed/")
        ):
            continue
        # Official Oita tourism lists many events unrelated to road stations.
        if spec.get("venue") and spec["venue"] not in title:
            continue
        options.setdefault(link, title)
    # Official municipal notice: fixed-venue and date source, not guessed.
    for seed in spec.get("seed", ()):
        options.setdefault(seed, "竹の千灯籠夜")
    return list(options.items())[:MAX_CANDIDATES]

def _get(url):
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    response.encoding = response.apparent_encoding if (response.encoding or "").lower() == "iso-8859-1" else response.encoding
    return BeautifulSoup(response.text, "html.parser")

def collect_six_kyushu_prefectures(today):
    records, audits = [], []
    for spec in SOURCES:
        stats = {"prefecture": spec["prefecture"], "roadName": spec["road"],
                 "source": spec["list"], "listingError": "", "candidates": 0,
                 "checked": 0, "accepted": 0, "past": 0, "noEventDate": 0,
                 "detailErrors": 0, "examples": [], "undatedSamples": []}
        try:
            listing = _get(spec["list"])
            candidates = _candidate_links(spec, listing, spec["list"])
        except requests.RequestException as exc:
            stats["listingError"] = type(exc).__name__ + ": " + str(exc)[:160]
            candidates = _candidate_links(spec, BeautifulSoup("", "html.parser"), spec["list"])
        stats["candidates"] = len(candidates)
        for url, headline in candidates:
            try:
                soup = _get(url)
            except requests.RequestException:
                stats["detailErrors"] += 1
                continue
            stats["checked"] += 1
            heading = soup.select_one("article h1") or soup.select_one("main h1") or soup.select_one("h1")
            article_title = clean(heading.get_text(" ", strip=True)) if heading else headline
            # Skip alerts/recruitment; only station-hosted public events count.
            if any(w in article_title for w in EXCLUDE):
                continue
            published = publication_date(soup, article_title)
            p = event_date_from_official_article(article_title, soup, published)
            if not p:
                stats["noEventDate"] += 1
                if len(stats["undatedSamples"]) < 3:
                    stats["undatedSamples"].append({"title": article_title[:100], "url": url})
                continue
            if p[1] < today.isoformat():
                stats["past"] += 1
                continue
            if spec.get("venue"):
                # Municipality/tourism sources are not station-owned. Both
                # the article and its stated event venue must identify the station.
                target = spec["venue"]
                body = clean((soup.select_one("article") or soup.select_one("main")
                              or soup).get_text(" ", strip=True))
                if target not in body or not re.search(r"(?:開催場所|開催地|会場)\s*[:：]?\s*"
                                                      + re.escape(target), body):
                    stats["noEventDate"] += 1
                    continue
            record = {"roadName": spec["road"], "prefecture": spec["prefecture"],
                      "title": article_title if any(w in article_title for w in EVENT_WORDS) else headline,
                      "startDate": p[0], "endDate": p[1],
                      "publishedAt": published.isoformat() if published else "",
                      "url": url, "status": "scheduled"}
            records.append(record)
            stats["accepted"] += 1
            if len(stats["examples"]) < 5:
                stats["examples"].append({"title": record["title"], "date": p[0], "url": url})
        audits.append(stats)
        print(f"九州6県 {spec['prefecture']}・{spec['road']}: "
              f"記事候補={stats['candidates']} 採用={stats['accepted']} "
              f"終了済={stats['past']} 日付不明={stats['noEventDate']} "
              f"取得失敗={stats['detailErrors']}")
    # The Nakatsu municipal notice and Oita tourism listing can describe the
    # same single festival. Keep the city source rather than double publishing.
    oita_city = [x for x in records if x["prefecture"] == "大分県"
                 and "city-nakatsu.jp" in x["url"]
                 and "竹の千灯籠夜" in x["title"]]
    if oita_city:
        city_dates = {(x["startDate"], x["endDate"]) for x in oita_city}
        records = [x for x in records if not (
            x["prefecture"] == "大分県"
            and "visit-oita.jp" in x["url"]
            and "竹の千灯籠夜" in x["title"]
            and (x["startDate"], x["endDate"]) in city_dates)]
    unique = {(x["prefecture"], x["roadName"], x["url"], x["startDate"]): x for x in records}
    audit = {"schemaVersion": 1, "sources": audits, "accepted": len(unique)}
    content = json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
    if not REPORT.exists() or REPORT.read_text(encoding="utf-8") != content:
        REPORT.write_text(content, encoding="utf-8")
    return list(unique.values())

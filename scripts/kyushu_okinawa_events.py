"""Conservative collectors for two verified Kyushu/Okinawa roadside-station sites.

Listing publication dates are never used as event dates. Each station is fixed
to its verified official domain; no cross-site venue inference is performed.
"""
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SOURCES = (
    {"name": "くるめ", "prefecture": "福岡県",
     "list": "https://www.michinoeki-kurume.com/category/event/",
     "home": "https://www.michinoeki-kurume.com/",
     "host": "www.michinoeki-kurume.com"},
    {"name": "かでな", "prefecture": "沖縄県",
     "list": "https://michinoeki-kadena.jp/news/",
     "home": "https://michinoeki-kadena.jp/",
     "host": "michinoeki-kadena.jp"},
)
AUDIT = Path(__file__).resolve().parents[1] / "data" / "kyushu_okinawa_event_audit.json"
HEADERS = {"User-Agent": "MichinotochuRoadEventBot/1.6 (station official event news; daily)"}
EVENT_TERMS = ("フェア", "フェスタ", "まつり", "祭", "イベント", "マルシェ",
               "公演", "コンサート", "音楽", "ワークショップ", "感謝祭", "開催",
               "チャレンジステーション", "ハロウィン", "展示", "販売会")
BLOCKED = ("中止", "延期", "臨時休業", "休館", "営業時間", "募集", "求人", "定休日",
           "交通規制", "工事", "中止のお知らせ")
MONTHLY_BULLETIN = re.compile(r"\d{1,2}月のイベント情報")
DATE_TOKEN = re.compile(
    r"(?:(20\d{2})年\s*)?(\d{1,2})月\s*(\d{1,2})日"
    r"(?:\s*[\(（]([月火水木金土日])(?:[^)）]{0,6})[\)）])?"
)
POST_DATE = re.compile(r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})日?")
WEEKDAYS = "月火水木金土日"
RANGE_SEP = re.compile(r"[～〜~▶▷\-－–]|から")
START_ONLY = re.compile(r"^\s*[～〜~▶▷\-－–]")

def clean(value):
    return " ".join(unicodedata.normalize("NFKC", value or "").split())

def date_from_parts(groups):
    try:
        return date(*map(int, groups))
    except (ValueError, TypeError):
        return None

def publication_date(soup, article_title=None):
    """Publication date only establishes the year of abbreviated event dates."""
    for meta in soup.select('meta[property="article:published_time"], meta[name="date"], meta[itemprop="datePublished"]'):
        match = POST_DATE.search(clean(meta.get("content", "")))
        if match:
            return date_from_parts(match.groups())
    for node in soup.select("time[datetime], article time, .post-date, .entry-date, .post-meta, .entry-meta, .date"):
        match = POST_DATE.search(clean(node.get("datetime", "") or node.get_text(" ", strip=True)))
        if match:
            return date_from_parts(match.groups())
    # Date-stamped nodes are frequently plain spans/divs with site-specific
    # classes, rather than <time> or the standard WordPress .entry-date class.
    for node in soup.select('[class*="date"], [class*="Date"], [class*="publish"], [class*="Publish"], [itemprop="datePublished"]'):
        value = clean(node.get("datetime", "") or node.get("content", "") or
                      node.get_text(" ", strip=True))
        if len(value) > 48:
            continue
        match = POST_DATE.search(value)
        if match:
            return date_from_parts(match.groups())
    # Article heading area only: never the full page, which contains other posts.
    for node in soup.select("article header, .entry-header"):
        match = POST_DATE.search(clean(node.get_text(" ", strip=True))[:200])
        if match:
            return date_from_parts(match.groups())
    # Final fallback: a *standalone full-year date line* immediately beside a
    # matching article heading. Do not take unrelated dates from the page body.
    if article_title:
        title = clean(article_title)
        lines = [clean(line) for line in soup.get_text("\\n", strip=True).splitlines()]
        for i, line in enumerate(lines):
            if len(title) < 7 or line != title:
                continue
            for nearby in lines[max(0, i-2):min(len(lines), i+5)]:
                label = re.sub(r"^(?:掲載日|投稿日|公開日|更新日)[：:]?\\s*", "", nearby)
                match = POST_DATE.fullmatch(label)
                if match:
                    return date_from_parts(match.groups())
    return None

def event_period(fragment, published):
    """Require one event-specific start; reject open-ended end-only periods."""
    if not published:
        return None
    value = clean(fragment)
    value = re.sub(r"^(?:【?期間】?|開催期間|開催日時|開催日|日程|日時)\s*[:：]?\s*", "", value)
    if START_ONLY.match(value):
        return None
    matches = list(DATE_TOKEN.finditer(value))
    if not matches or len(matches) > 2:
        return None
    def read(m, after=None):
        y = int(m.group(1)) if m.group(1) else published.year
        month, day = int(m.group(2)), int(m.group(3))
        if not m.group(1) and published.month >= 11 and month <= 2:
            y += 1
        if after and not m.group(1) and month < after.month:
            y = after.year + 1
        d = date_from_parts((y, month, day))
        if d and m.group(4) and WEEKDAYS[d.weekday()] != m.group(4):
            return None
        return d
    first = read(matches[0])
    if not first:
        return None
    last = first
    if len(matches) == 2:
        between = value[matches[0].end():matches[1].start()]
        if len(between) > 20 or not RANGE_SEP.search(between):
            return None
        last = read(matches[1], first)
    if not last or first > last or last < published or (last - first).days > 120:
        return None
    return first.isoformat(), last.isoformat()

def article_event_period(soup, title, published):
    """Inspect only explicitly labelled date lines in the article body."""
    p = event_period(title, published)
    if p:
        return p
    main = (soup.select_one(".entry-content") or soup.select_one(".post-content")
            or soup.select_one("article .content") or soup.select_one("article")
            or soup.select_one("main"))
    if not main:
        return None
    for node in main.select("p, li, dd, td, h2, h3"):
        line = clean(node.get_text(" ", strip=True))
        if len(line) > 250 or not re.search(r"^(?:【?期間】?|開催期間|開催日時|開催日|日程|日時)\s*[:：]?", line):
            continue
        p = event_period(line, published)
        if p:
            return p
    return None

def _article_candidates(soup, spec):
    found = {}
    for anchor in soup.select("a[href]"):
        title = clean(anchor.get_text(" ", strip=True))
        if not 7 <= len(title) <= 140:
            continue
        if not any(word in title for word in EVENT_TERMS):
            continue
        if any(word in title for word in BLOCKED) or MONTHLY_BULLETIN.search(title):
            continue
        href = urljoin(spec["list"], anchor["href"])
        parsed = urlparse(href)
        if parsed.scheme != "https" or parsed.hostname != spec["host"]:
            continue
        if spec["name"] == "かでな" and not re.fullmatch(r"/news/n\d+\.html", parsed.path):
            continue
        if spec["name"] == "くるめ":
            if parsed.path.startswith(("/category/", "/tag/", "/page/", "/wp-")):
                continue
            if parsed.path == "/":
                continue
        found.setdefault(href, title)
    # Keep the list bounded and stable; old events are removed by date checks.
    return list(found.items())[:18]

def collect_kyushu_okinawa(today):
    results = []
    report = {"schemaVersion": 1, "sources": [], "accepted": 0}
    for spec in SOURCES:
        stats = {"station": spec["name"], "prefecture": spec["prefecture"],
                 "listUrl": spec["list"], "candidates": 0, "checked": 0,
                 "accepted": 0, "noDate": 0, "missingPublication": 0,
                 "missingEventDate": 0, "past": 0, "failed": 0,
                 "sampleMissingPublication": [], "sampleMissingEventDate": [],
                 "sampleAccepted": [], "error": ""}
        try:
            res = requests.get(spec["list"], headers=HEADERS, timeout=18)
            res.raise_for_status()
            res.encoding = res.apparent_encoding if res.encoding and res.encoding.lower() == "iso-8859-1" else res.encoding
            listing = BeautifulSoup(res.text, "html.parser")
            candidates = _article_candidates(listing, spec)
            # Verified direct official notice; ensures initial coverage even if
            # newer listing entries push this post beyond the first page.
            if spec["name"] == "くるめ":
                url = "https://www.michinoeki-kurume.com/shinmaifair/"
                if not any(href == url for href, _ in candidates):
                    candidates.append((url, "【イベント情報】新米フェアのお知らせ"))
            stats["candidates"] = len(candidates)
            stats["sampleCandidates"] = [{"title": title, "url": url} for url, title in candidates[:8]]
            for url, title in candidates:
                try:
                    r = requests.get(url, headers=HEADERS, timeout=12)
                    r.raise_for_status()
                    r.encoding = r.apparent_encoding if r.encoding and r.encoding.lower() == "iso-8859-1" else r.encoding
                    detail = BeautifulSoup(r.text, "html.parser")
                except requests.RequestException:
                    stats["failed"] += 1
                    continue
                stats["checked"] += 1
                published = publication_date(detail, title)
                if not published:
                    stats["noDate"] += 1
                    stats["missingPublication"] += 1
                    if len(stats["sampleMissingPublication"]) < 4:
                        stats["sampleMissingPublication"].append({
                            "title": title, "url": url,
                            "headingText": clean(detail.select_one("h1").get_text(" ", strip=True))
                            if detail.select_one("h1") else "",
                            "dateClassNames": [str(node.get("class")) for node in detail.select(
                                '[class*="date"], [class*="Date"]')[:6]],
                        })
                    continue
                p = article_event_period(detail, title, published)
                if not p:
                    stats["noDate"] += 1
                    stats["missingEventDate"] += 1
                    if len(stats["sampleMissingEventDate"]) < 4:
                        stats["sampleMissingEventDate"].append({
                            "title": title, "url": url, "published": published.isoformat(),
                            "articleSample": clean((detail.select_one(".entry-content") or
                                detail.select_one("article") or detail.select_one("main") or
                                detail).get_text(" ", strip=True))[:270]
                        })
                    continue
                if p[1] < today.isoformat():
                    stats["past"] += 1
                    continue
                results.append({"roadName": spec["name"], "prefecture": spec["prefecture"],
                                "title": title, "startDate": p[0], "endDate": p[1],
                                "publishedAt": published.isoformat(), "url": url,
                                "status": "scheduled"})
                stats["accepted"] += 1
                stats["sampleAccepted"].append({"title": title, "start": p[0], "end": p[1]})
        except requests.RequestException as exc:
            stats["error"] = type(exc).__name__ + ": " + str(exc)[:170]
        print(f"九州沖縄公式 {spec['name']}: 候補 {stats['candidates']} / "
              f"取得 {stats['checked']} / 採用 {stats['accepted']} / "
              f"日付未確定 {stats['noDate']} / 終了済 {stats['past']} / "
              f"取得失敗 {stats['failed']}")
        report["sources"].append(stats)
    # Avoid duplicating one article across listing appearances.
    dedup = {(e["roadName"], e["url"]): e for e in results}
    report["accepted"] = len(dedup)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if not AUDIT.exists() or AUDIT.read_text(encoding="utf-8") != payload:
        AUDIT.write_text(payload, encoding="utf-8")
    return list(dedup.values())

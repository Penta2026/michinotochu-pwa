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
DATE_LABEL = re.compile(r"(?:開催日(?:時|程)?|開催期間|イベント日時|日程|日時|開催予定|実施日|日にち)\s*[:：]?\s*")
VENUE_LABEL = re.compile(r"^(?:開催場所|会場|開催地|会場名|開催会場)\s*[:：]?\s*")
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
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.username or parsed.password or
            parsed.port is not None or parsed.hostname not in source["allowedHosts"]):
        return False
    if article and not re.fullmatch(source["articlePathPattern"], parsed.path):
        return False
    return True

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
    if container is None:
        return ""
    for selector in spec["titleSelectors"]:
        node = soup.select_one(selector)
        if node and (node is container or node in container.descendants):
            txt = clean(node.get_text(" ", strip=True))
            if any(w in txt for w in EVENT_WORDS) and not any(w in txt for w in BLOCK):
                return txt
    fallback = PUBLICATION_PREFIX.sub("", clean(listing_title))
    return fallback if any(w in fallback for w in EVENT_WORDS) else ""

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

def _article_record(source, soup, listing_title, today, url):
    article = _pick_article(soup, source)
    if article is None:
        return None, "no_article"
    title = _headline(soup, source, listing_title)
    if not title or any(w in title for w in BLOCK):
        return None, "not_event"
    if not any(w in title for w in EVENT_WORDS):
        return None, "not_event"
    lines = _article_lines(article, source)
    body = clean(article.get_text(" ", strip=True))
    if not any(w in body for w in source["requiredVenueTokens"]):
        return None, "venue_missing"
    for line in lines:
        if VENUE_LABEL.search(line):
            if not any(w in line for w in source["requiredVenueTokens"]):
                return None, "offsite"
    posted = publication_date(soup, title)
    # A future "published" date is usually a mislabeled event date.
    if posted and posted > today:
        posted = None
    period = _article_period(title, lines, posted)
    if period is None:
        return None, "undated"
    if period[1] < today.isoformat():
        return None, "past"
    return {"roadName": source["roadName"], "prefecture": source["prefecture"],
            "title": title, "startDate": period[0], "endDate": period[1],
            "publishedAt": posted.isoformat() if posted else "", "url": url,
            "status": "scheduled"}, "accepted"

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
            if url in known_urls or url in newly_seen:
                summary["knownSkipped"] += 1
                continue
            if summary["checked"] >= int(spec.get("maxArticles", 6)):
                break
            try:
                detail = fetch(url)
            except (requests.RequestException, ValueError, AttributeError):
                summary["fetchFailed"] += 1
                continue
            summary["checked"] += 1
            record, why = _article_record(spec, detail, text, today, url)
            if record:
                records.append(record)
                newly_seen.add(url)
                summary["accepted"] += 1
                if len(summary["examples"]) < 5:
                    summary["examples"].append({"title": record["title"],
                                                "start": record["startDate"],
                                                "end": record["endDate"],
                                                "url": record["url"]})
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

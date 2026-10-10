"""Registry-driven reconfirmation of *already verified* official station events.

Phase 1 of reusable station adapters. Unlike event discovery, this module can
never create a date, title, or venue: it reuses a previously published record
only after a fresh official article matches BOTH event text and event period.
Registry controls station identity, official hosts and URL patterns.
"""
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from kanto_remaining_prefectures import event_period, DATE_TOKEN
from road_event_quality import identity, plausible

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "data" / "verified_station_source_rules.json"
REPORT = ROOT / "data" / "verified_station_reconfirmation_audit.json"
HEADERS = {"User-Agent": "MichinotochuRoadEventBot/2.1 (verified official article reconfirmation)"}
SKIP = ("中止", "開催中止", "開催延期")

def _normal(value):
    return re.sub(r"[^\w]+", "", unicodedata.normalize("NFKC", value or "").casefold())

def _subject(title):
    """Keep the distinctive event name, excluding posting date/venue boilerplate."""
    t = unicodedata.normalize("NFKC", title or "")
    quotes = re.findall(r"[『「]([^』」]{4,80})[』」]", t)
    # For notices like 【イベント】10/24『ハロウィンマーケット』,
    # distinguish the event from generic official category labels.
    names = [x for x in quotes if "道の駅" not in x or len(x) <= 15]
    if names:
        t = names[-1]
    else:
        t = re.sub(r"^[「『]道の駅[^」』]+[」』]\s*", "", t)
        t = re.sub(r"^(?:20\d{2}[./年]\d{1,2}[./月]\d{1,2}日?\s*)+", "", t)
        t = re.sub(r"^[\[【]?(?:イベント|EVENT|お知らせ)[\]】]?\s*", "", t, flags=re.I)
        t = re.sub(r"[(（]\s*20\d{2}[^)）]*[)）]", "", t)
        t = re.sub(r"(?:を開催します|開催のお知らせ|開催します|のご案内)\s*(?:NEW)?$", "", t)
    return _normal(t)

def _rule_for(record, rules):
    url = urlparse(record.get("url", ""))
    if url.scheme != "https" or url.username or url.password or url.port:
        return None
    for rule in rules:
        if (record.get("prefecture") == rule["prefecture"] and
            record.get("roadName") == rule["roadName"] and
            url.hostname in rule["allowedHosts"] and
            re.fullmatch(rule["pathPattern"], url.path)):
            return rule
    return None

def _event_segments(soup):
    container = soup.select_one("article") or soup.select_one("main")
    if container is None:
        return []
    for excluded in container.select("nav, footer, aside, script, style"):
        excluded.decompose()
    segments = []
    for node in container.select("h1,h2,h3,h4,p,li,dt,dd,td"):
        # Avoid extracting a whole nested event-list as one segment.
        if node.find_parent(["nav","footer","aside"]):
            continue
        value = " ".join(node.get_text(" ", strip=True).split())
        if 5 <= len(value) <= 420 and value not in segments:
            segments.append(value)
    return segments[:100]

def _date_appears_in_event_context(segments, record):
    """The expected date/range must be spelled out in article text.

    The previously verified start year is used only to parse omitted years.
    This never authorizes a new event, or a different future date.
    """
    expected = (record.get("startDate"), record.get("endDate"))
    grounded = date.fromisoformat(expected[0])
    for segment in segments:
        # Limit full page metadata false positives: do not count just an
        # unrelated "last updated" date or the site's event navigation.
        if any(x in segment for x in ("関連記事", "投稿一覧", "アーカイブ")):
            continue
        for m in DATE_TOKEN.finditer(unicodedata.normalize("NFKC", segment)):
            txt = unicodedata.normalize("NFKC", segment)[m.start():]
            parsed = event_period(txt, grounded)
            if parsed == expected:
                return True
    return False

def _confirm(record, html):
    soup = BeautifulSoup(html, "html.parser")
    segments = _event_segments(soup)
    if not segments:
        return False, "no_article_content"
    subject = _subject(record.get("title", ""))
    full = _normal(" ".join(segments))
    if len(subject) < 4 or subject not in full:
        # Distinctive quoted names can be a better match than boilerplate
        # titles; never accept an empty/generic title.
        return False, "title_not_found"
    if any(w in segments[0] for w in SKIP):
        return False, "cancelled_or_postponed"
    if not _date_appears_in_event_context(segments, record):
        return False, "date_not_reconfirmed"
    return True, "reconfirmed"

def _fetch_default(url):
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=Retry(total=1, connect=1, read=0, backoff_factor=0.2)))
    response = session.get(url, headers=HEADERS, timeout=(4, 9), allow_redirects=False)
    response.raise_for_status()
    if response.status_code != 200:
        raise requests.RequestException(f"Unexpected HTTP status {response.status_code}")
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding
    return response.text

def reconfirm_known_articles(today, previous, collected, rules=None, fetch=None, report_path=REPORT):
    """Re-collect only a previous, plausible event missed by all regular feeds.

    Returns copies of existing verified records; never invents new events.
    When upstream is down, preserve the old record through normal reconcile
    and report a distinct fetch failure instead of claiming reconfirmation.
    """
    if rules is None:
        config = json.loads(RULES.read_text(encoding="utf-8"))
        if config.get("schemaVersion") != 1:
            raise ValueError("Unrecognized official source registry schema")
        rules = config["sources"]
    fetch = fetch or _fetch_default
    gathered = {identity(x) for x in collected if plausible(x, today)}
    again = []
    audit = {"schemaVersion": 1, "checked": 0, "reconfirmed": 0,
             "alreadyCollected": 0, "outsideRegistry": 0, "failed": 0,
             "inconclusive": 0, "sources": {},"checks": []}
    for event in previous:
        if not plausible(event, today):
            continue
        if identity(event) in gathered:
            audit["alreadyCollected"] += 1
            continue
        rule = _rule_for(event, rules)
        if rule is None:
            audit["outsideRegistry"] += 1
            continue
        audit["checked"] += 1
        key = rule["id"]
        source_stats = audit["sources"].setdefault(key, {"checked": 0, "reconfirmed": 0,
                                                         "failed": 0, "inconclusive": 0})
        source_stats["checked"] += 1
        status = "inconclusive"
        try:
            html = fetch(event["url"])
            ok, detail = _confirm(event, html)
            if ok:
                again.append(dict(event))
                gathered.add(identity(event))
                audit["reconfirmed"] += 1
                source_stats["reconfirmed"] += 1
                status = "reconfirmed"
            else:
                audit["inconclusive"] += 1
                source_stats["inconclusive"] += 1
                status = detail
        except (requests.RequestException, ValueError, UnicodeError) as exc:
            audit["failed"] += 1
            source_stats["failed"] += 1
            status = f"fetch_failed:{type(exc).__name__}"
        audit["checks"].append({"station": event["roadName"], "prefecture": event["prefecture"],
                                "title": event["title"], "url": event["url"], "result": status})
    payload = json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
    if report_path is not None:
        if not report_path.exists() or report_path.read_text(encoding="utf-8") != payload:
            report_path.write_text(payload, encoding="utf-8")
    print("共通公式記事再確認: 対象 %s / 再確認 %s / 取得失敗 %s / 不確定 %s / 設定対象外 %s" %
          (audit["checked"], audit["reconfirmed"], audit["failed"],
           audit["inconclusive"], audit["outsideRegistry"]))
    return again, audit

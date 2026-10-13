"""Nationwide official regional-source discovery and diagnostics.

Discovery is deliberately not a publication parser: many associations publish
PDF calendars, regional fairs, opening announcements, or non-station events.
Only verified event records should enter road_events.json via source adapters.
"""
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "road_event_sources_report.json"
SOURCES = [
    {"region": "北海道", "url": "https://hokkaido-michinoeki.jp/", "status": "discovery"},
    {"region": "東北", "url": "https://www.michinoeki-tohoku.com/event", "status": "adapter"},
    {"region": "関東", "url": "https://www.kanto-michinoeki.jp/", "status": "discovery"},
    {"region": "北陸", "url": "https://www.hokuriku-michinoeki.jp/", "status": "discovery"},
    {"region": "中部", "url": "https://www.chubu-michinoeki.org/", "status": "discovery"},
    {"region": "近畿", "url": "https://www.kinki-michinoeki.com/news-tag/event/", "status": "adapter"},
    {"region": "中国", "url": "https://chugoku-michinoeki.jp/news/index.php", "status": "adapter"},
    {"region": "四国", "url": "https://www.sk-michinoeki.jp/events", "status": "adapter"},
    {"region": "九州・沖縄", "url": "https://www.qsr.mlit.go.jp/n-michi/michi_no_eki/", "status": "discovery"},
]
# Curated, same-host event-category listings; these are discovery only.
# Do not treat category pages or their links as verified future events.
SECONDARY_EVENT_LISTINGS = {
    "関東": "https://www.kanto-michinoeki.jp/archives/category/%e3%82%a4%e3%83%99%e3%83%b3%e3%83%88%e6%83%85%e5%a0%b1",
}
KEYWORDS = ("イベント", "催し", "祭", "フェス", "マルシェ", "催事", "開催", "カレンダー")
EXCLUDE = ("ログイン", "プライバシー", "お問い合わせ", "スタンプラリー", "会社概要")
HEADERS = {"User-Agent": "MichinotochuRoadEventBot/1.3 (official link audit; daily)"}

def scan_event_listing(url, fetch=requests.get):
    """Read one curated official category, with robots policy and bounded URL checks."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Invalid official event listing URL")
    robots = f"{parsed.scheme}://{parsed.hostname}/robots.txt"
    policy_response = fetch(robots, timeout=12, headers=HEADERS, allow_redirects=False)
    if policy_response.status_code == 200:
        rp = RobotFileParser()
        rp.parse(policy_response.text.splitlines())
        if not rp.can_fetch(HEADERS["User-Agent"], url):
            return {"state": "robots_disallowed", "candidateCount": 0}
    elif policy_response.status_code != 404:
        return {"state": "robots_unknown", "candidateCount": 0}
    res = fetch(url, timeout=12, headers=HEADERS, allow_redirects=False)
    if res.status_code != 200 or len(res.content) > 750_000:
        return {"state": "fetch_failed_or_oversize", "candidateCount": 0}
    soup = BeautifulSoup(res.text, "html.parser")
    links = set()
    for a in soup.select("a[href]"):
        href = urljoin(url, a["href"])
        p = urlparse(href)
        if p.scheme != "https" or p.hostname != parsed.hostname or p.username or p.password:
            continue
        title = " ".join(a.get_text(" ", strip=True).split())
        if len(title) < 8 or not any(w in title for w in KEYWORDS) or any(w in title for w in EXCLUDE):
            continue
        if href != url:
            links.add(href)
        if len(links) >= 35:
            break
    return {"state": "inspected", "candidateCount": len(links),
            "candidateUrlsUnverified": sorted(links)}


def match_station_hints(report, roads):
    """Annotate article candidates with unique IDs; never infer an event."""
    from station_coverage_registry import station_key
    lookup = {}
    for road in roads:
        lookup.setdefault(station_key(road["prefecture"], road["name"])[1], []).append(road)
    for source in report["sources"]:
        for candidate in source.get("candidates", []):
            title = candidate.get("title", "")
            names = re.findall(r"【([^】]+)】", title)
            hits = {}
            for name in names:
                for road in lookup.get(station_key("", name.replace("道の駅", ""))[1], []):
                    hits[road["id"]] = road
            candidate["stationIdHint"] = next(iter(hits)) if len(hits) == 1 else ""
            candidate["identityStatus"] = ("single_station_hint" if len(hits) == 1
                                           else "ambiguous" if len(hits) > 1
                                           else "unmatched")
            candidate["eventVerified"] = False
    return report

def audit_sources(now=None):
    now = now or datetime.now()
    result = {"checkedAt": now.isoformat(timespec="seconds"), "sources": []}
    for source in SOURCES:
        item = dict(source)
        item.update({"reachable": False, "candidates": [], "candidateCount": 0, "error": ""})
        try:
            r = requests.get(source["url"], timeout=12, headers=HEADERS)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            host = urlparse(r.url).hostname or ""
            seen = set()
            for anchor in soup.select("a[href]"):
                title = " ".join(anchor.get_text(" ", strip=True).split())
                href = urljoin(r.url, anchor.get("href", ""))
                parsed = urlparse(href)
                if parsed.scheme not in ("http", "https"):
                    continue
                if not (parsed.hostname == host or (parsed.hostname or "").endswith("." + host)):
                    continue
                # retain PDFs as review candidates; never interpret PDFs as HTML
                if not any(word in title for word in KEYWORDS) or any(word in title for word in EXCLUDE):
                    continue
                if not 4 <= len(title) <= 150 or href in seen:
                    continue
                seen.add(href)
                item["candidates"].append({"title": title, "url": href})
                if len(item["candidates"]) >= 35:
                    break
            item["reachable"] = True
            item["candidateCount"] = len(item["candidates"])
        except (requests.RequestException, ValueError) as exc:
            item["error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
        if source["region"] in SECONDARY_EVENT_LISTINGS:
            listing_url = SECONDARY_EVENT_LISTINGS[source["region"]]
            try:
                item["curatedEventListing"] = {"url": listing_url,
                    **scan_event_listing(listing_url)}
            except (requests.RequestException, ValueError) as exc:
                item["curatedEventListing"] = {"url": listing_url,
                    "state": "inspection_error", "candidateCount": 0,
                    "error": type(exc).__name__}
        result["sources"].append(item)
        print(f"地域監査 {source['region']}: 接続={'OK' if item['reachable'] else 'NG'} / "
              f"公式告知候補={item['candidateCount']} / 公開解析={source['status']}")
    from station_coverage_registry import DATA, read_app_stations
    roads = read_app_stations((DATA / "app_data.js").read_text(encoding="utf-8"))
    match_station_hints(result, roads)
    previous = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    # Avoid changing git history every day when only the scan timestamp differs.
    stable = {"schemaVersion": 1, "sources": result["sources"]}
    if previous != stable:
        REPORT.write_text(json.dumps(stable, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result

if __name__ == "__main__":
    audit_sources()

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
KEYWORDS = ("イベント", "催し", "祭", "フェス", "マルシェ", "催事", "開催", "カレンダー")
EXCLUDE = ("ログイン", "プライバシー", "お問い合わせ", "スタンプラリー", "会社概要")
HEADERS = {"User-Agent": "MichinotochuRoadEventBot/1.3 (official link audit; daily)"}

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
        result["sources"].append(item)
        print(f"地域監査 {source['region']}: 接続={'OK' if item['reachable'] else 'NG'} / "
              f"公式告知候補={item['candidateCount']} / 公開解析={source['status']}")
    previous = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    # Avoid changing git history every day when only the scan timestamp differs.
    stable = {"schemaVersion": 1, "sources": result["sources"]}
    if previous != stable:
        REPORT.write_text(json.dumps(stable, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result

if __name__ == "__main__":
    audit_sources()

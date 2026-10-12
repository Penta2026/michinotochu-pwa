"""Build a per-station official-event coverage register for ALL app road stations.

This is an inventory, not a generic web scraper or a measure of true recall.
An unconfigured station is 'unverified', NEVER 'no events'.
Existing official collection adapters continue to be the only publisher.
"""
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "station_coverage_registry.json"
DASHBOARD = ROOT / "docs" / "STATION_COVERAGE_DASHBOARD.md"
JST = timezone(timedelta(hours=9))
WEB_FIELDS = ("officialUrl", "officialURL", "officialSite", "website", "websiteUrl",
              "homepage", "homePage", "home_url", "hp", "url")
SKIP_HOSTS = ("maps.google.com", "google.com", "maps.app.goo.gl", "facebook.com",
              "instagram.com", "x.com", "twitter.com", "youtube.com")


def station_key(prefecture, name):
    name = unicodedata.normalize("NFKC", name or "")
    name = re.sub(r"^道の駅\s*", "", name)
    name = re.sub(r"[\s・･_‐‑–—－-]+", "", name)
    return prefecture or "", name


def read_app_stations(raw):
    """Parse JSON after APP_DATA assignment; never evaluate JavaScript."""
    marker = "window.APP_DATA="
    loc = raw.find(marker)
    if loc < 0:
        raise ValueError("APP_DATA assignment missing")
    obj, _ = json.JSONDecoder().raw_decode(raw[loc + len(marker):].lstrip())
    roads = obj.get("roads")
    if not isinstance(roads, list) or not roads:
        raise ValueError("Road-station master empty")
    expected = obj.get("meta", {}).get("roadStations")
    if expected is not None and expected != len(roads):
        raise ValueError("Road-station master length mismatch")
    codes = set()
    for road in roads:
        if not road.get("id") or not road.get("name") or not road.get("prefecture"):
            raise ValueError("Road-station identity incomplete")
        if road["id"] in codes:
            raise ValueError("Duplicate station ID")
        codes.add(road["id"])
    return roads


def website_candidates(road):
    """Hints only. A URL embedded in app data is NOT automatically official."""
    urls = set()
    for key in WEB_FIELDS:
        value = road.get(key)
        if not isinstance(value, str):
            continue
        parsed = urlparse(value.strip())
        host = (parsed.hostname or "").lower()
        if (parsed.scheme != "https" or not host or parsed.username
                or parsed.password or parsed.port is not None
                or any(host == banned or host.endswith("." + banned)
                       for banned in SKIP_HOSTS)):
            continue
        urls.add(value.strip())
    return sorted(urls)


def build_inventory(roads, sources, reconfirm, events, audit, *, checked_on, coverage=None,
                    directory=None):
    """Every station must receive a result, including 0-event or unknown sites."""
    indexed = {}
    for source in sources.get("sources", []):
        if source.get("enabled", False):
            indexed.setdefault(station_key(source.get("prefecture"),
                                           source.get("roadName")), []).append(source)
    recheck = {}
    for source in reconfirm.get("sources", []):
        recheck.setdefault(station_key(source.get("prefecture"),
                                       source.get("roadName")), []).append(source["id"])
    # Include older, explicitly targeted collection adapters tracked in
    # the 47-prefecture audit; the two JSON registries are NOT all collectors.
    known_targets = {
        station_key(item.get("prefecture"), name)
        for item in (coverage or {}).get("prefectures", [])
        for name in item.get("targetedStationFeeds", [])
    }
    audits = {s["id"]: s for s in audit.get("sources", [])}
    verified_directory = {}
    for found in (directory or {}).get("stations", []):
        code = found.get("id")
        if code in verified_directory:
            raise ValueError("Duplicate station ID in directory hints")
        verified_directory[code] = found
    verified_events = Counter(
        station_key(e.get("prefecture"), e.get("roadName"))
        for e in events.get("events", []))
    items = []
    seen = set()
    for road in roads:
        code = road["id"]
        if code in seen:
            raise ValueError("Duplicate station ID")
        seen.add(code)
        key = station_key(road["prefecture"], road["name"])
        feeds = indexed.get(key, [])
        audited = [audits[x["id"]] for x in feeds if x["id"] in audits]
        directory_item = verified_directory.get(code)
        directory_checked = bool(
            directory_item and station_key(directory_item.get("prefecture"),
                                           directory_item.get("roadName")) == key)
        # Station-directory homepages are suggestions, NOT verified site ownership.
        directory_hints = (directory_item.get("officialWebsiteCandidateUrlsUnverified", [])
                           if directory_checked else [])
        candidates = sorted(set(website_candidates(road) + list(directory_hints)))
        covered_any = key in known_targets or bool(feeds or recheck.get(key))
        if verified_events[key]:
            state = "current_official_event_verified"
        elif audited:
            state = "dedicated_source_checked_no_verified_future_event"
        elif feeds or recheck.get(key):
            state = "dedicated_source_configured_not_checked"
        elif covered_any:
            state = "other_dedicated_collector_configured"
        else:
            state = "no_dedicated_source"
        items.append({
            "id": code, "prefecture": road["prefecture"], "roadName": road["name"],
            "coverageState": state,
            "officialWebsiteCandidateUrlsUnverified": candidates,
            "directoryDetailUrl": (directory_item.get("directoryDetailUrl", "")
                                   if directory_checked else ""),
            "lastDirectoryChecked": (directory_item.get("lastDirectoryChecked", "")
                                     if directory_checked else ""),
            "officialSiteOwnershipVerified": False,
            "dedicatedSourceIds": [s["id"] for s in feeds],
            "dedicatedOfficialListingUrls": [s["listingUrl"] for s in feeds],
            "knownArticleRecheckSourceIds": recheck.get(key, []),
            "dedicatedCollectorCoveredAcrossAllModes": covered_any,
            "latestSourceAuditOn": audit.get("checkedOn", "") if audited else "",
            "latestSourceFetchFailed": sum(s.get("fetchFailed", 0) for s in audited),
            "latestSourceListingErrors": [s["listingError"] for s in audited
                                          if s.get("listingError")],
            "currentVerifiedEvents": verified_events[key],
            "eventAbsentConfirmed": False,
            "nextAction": ("verify_station_site_candidate" if candidates and not covered_any
                           else "review_official_website_url" if not covered_any
                           else "continue_verified_source_checks"),
        })
    totals = Counter(x["coverageState"] for x in items)
    summary = {
        "appStations": len(items),
        "individualSourcesWithListing": sum(bool(x["dedicatedSourceIds"]) for x in items),
        "individualSourcesIncludingRecheck": sum(bool(x["dedicatedSourceIds"] or
                                                      x["knownArticleRecheckSourceIds"])
                                                for x in items),
        "stationsWithCurrentVerifiedEvent": sum(x["currentVerifiedEvents"] > 0
                                                 for x in items),
        "currentVerifiedEventRecords": sum(x["currentVerifiedEvents"] for x in items),
        "stationsWithAnyDedicatedCollector": sum(
            x["dedicatedCollectorCoveredAcrossAllModes"] for x in items),
        "stationsWithoutDedicatedSource": sum(
            not x["dedicatedCollectorCoveredAcrossAllModes"] for x in items),
        "masterWebsiteUrlCandidatesUnverified": sum(bool(x["officialWebsiteCandidateUrlsUnverified"])
                                                    for x in items),
        "nationalDirectoryStationPagesChecked": sum(bool(x["lastDirectoryChecked"])
                                                     for x in items),
        "nationalDirectoryLinkCandidateStations": sum(
            bool(x["officialWebsiteCandidateUrlsUnverified"]) and bool(x["directoryDetailUrl"])
            for x in items),
        "statuses": dict(sorted(totals.items())),
        "confirmedNoEventStations": 0,
        "allStationRecordsPresent": len(items) == len(roads),
    }
    return {"schemaVersion": 1, "checkedOn": checked_on,
            "method": "inventory_only_official_urls_are_not_crawled_by_this_report",
            "limitations": [
                "This register covers all app station identities, not all their websites.",
                "No URL candidate is trusted without validation as a station official site.",
                "No matching event is NOT evidence that the station holds no event.",
                "Regional association collectors may cover stations without a dedicated feed.",
                "Captured station share is not national event recall.",
            ], "summary": summary, "stations": items}


def render_dashboard(register):
    s = register["summary"]
    lines = [
        "# 全国1,234駅・公式イベント巡回台帳",
        "",
        "更新日: " + register["checkedOn"],
        "",
        "> この台帳は **すべての駅を管理対象にしたもの**です。"
        " **すべての駅の公式サイトを実際に見に行った**という意味ではありません。",
        "> 「現在の登録イベント0件」「個別収集先なし」を"
        " **イベントが存在しない**と判断しません。",
        "",
        "## 駅単位の進捗",
        "",
        "| 指標 | 駅数 |", "|---|---:|",
        f"| アプリに登録済みの駅 | {s['appStations']} |",
        f"| 個別のイベント一覧巡回ルートあり | {s['individualSourcesWithListing']} |",
        f"| 新型エンジン＋既存記事の確認設定 | {s['individualSourcesIncludingRecheck']} |",
        f"| 既存の地域別専用収集も含む設定済み駅 | {s['stationsWithAnyDedicatedCollector']} |",
        f"| 現在、開催予定が検証・公開済みの駅 | {s['stationsWithCurrentVerifiedEvent']} |",
        f"| 個別の公式情報ルート未設定 | {s['stationsWithoutDedicatedSource']} |",
        f"| 駅マスタ＋公式名簿由来のサイト候補（未検証） | {s['masterWebsiteUrlCandidatesUnverified']} |",
        f"| 全国連絡会の駅詳細ページ照合済み | {s['nationalDirectoryStationPagesChecked']} |",
        f"| 全国連絡会からホームページ欄を取得（未検証） | {s['nationalDirectoryLinkCandidateStations']} |",
        f"| 検証済み『開催イベントなし』 | {s['confirmedNoEventStations']}（未判定） |",
        "",
        "## 次の一手",
        "",
        "1. 各駅の実際の公式サイトURLを照合し、確定URLだけ駅IDへ結び付ける。",
        "2. 公式サイトが分かった駅をローテーション巡回して"
        "『アクセス成功・候補検出・日時会場未確認・イベント確定・取得失敗』を記録。",
        "3. 公開には既存の厳格なイベント検証（公式URL、開催日、駅構内会場、中止判定）を使用。",
        "4. 1,234駅すべての最終巡回日・URL不足を記録した後、毎週の巡回完了率を算出。",
        "",
        "## 未設定駅について",
        "",
        "全駅の状態一覧は `data/station_coverage_registry.json` を参照。"
        "収集ルートを持たない駅も除外せず、駅ID単位で管理する。",
        "",
    ]
    return "\n".join(lines)


def write_if_changed(path, text):
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def main():
    from datetime import date
    roads = read_app_stations((DATA / "app_data.js").read_text(encoding="utf-8"))
    def get(name):
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    audit = get("station_event_discovery_audit.json")
    result = build_inventory(roads, get("station_event_discovery_sources.json"),
                             get("verified_station_source_rules.json"),
                             get("road_events.json"), audit,
                             coverage=get("prefecture_event_coverage.json"),
                             directory=(json.loads((DATA / "station_official_directory_candidates.json").read_text(
                                 encoding="utf-8"))
                                 if (DATA / "station_official_directory_candidates.json").exists() else {}),
                             checked_on=audit.get("checkedOn") or
                             datetime.now(JST).date().isoformat())
    write_if_changed(OUT, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    write_if_changed(DASHBOARD, render_dashboard(result))
    print("駅別台帳: 全{}駅 / 新規記事巡回{}駅 / 再確認も含む{}駅 / 掲載実績{}駅 / URL候補{}駅".format(
        result["summary"]["appStations"],
        result["summary"]["individualSourcesWithListing"],
        result["summary"]["individualSourcesIncludingRecheck"],
        result["summary"]["stationsWithCurrentVerifiedEvent"],
        result["summary"]["masterWebsiteUrlCandidatesUnverified"]))


if __name__ == "__main__":
    main()

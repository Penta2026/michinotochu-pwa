#!/usr/bin/env python3
"""Detect plausible event-collection blind spots without inventing events.

Consumes *existing* official-article audits; it does not scrape websites,
interpret image text, or estimate nationwide event recall. This is a
triage/health report, not a list of verified upcoming events.
"""
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
OUTPUT = DATA / "road_event_gap_monitor.json"
JST = timezone(timedelta(hours=9))

# Intentional conservative queue: an offsite or past notice is not a missing
# road-station event. Site-wide calendar image notices merit human review.
REVIEW_REASONS = {
    "undated": ("event_date_unverified", "high"),
    "venue_missing": ("onsite_venue_unverified", "high"),
    "no_individually_dated_sections": ("event_sections_unparsed", "high"),
    "no_individually_dated_monthly_events": ("monthly_events_unparsed", "high"),
    "no_grounded_program_year": ("event_year_unverified", "high"),
    "no_official_dated_station_rows": ("schedule_rows_unparsed", "medium"),
    "no_strictly_dated_news_notice": ("notice_date_or_venue_unverified", "medium"),
    "no_strict_official_calendar_cards": ("calendar_cards_unparsed", "medium"),
}
CALENDAR_TERMS = ("イベントカレンダー", "イベントスケジュール", "月間予定", "イベント情報")


def _positive_int(value):
    try:
        return max(0, int(value))
    except (ValueError, TypeError):
        return 0


def _day_streak(previous, key, active, today):
    if not active:
        return 0
    before = _positive_int(previous.get(key))
    # Do not count multiple manual workflow runs as multiple calendar days.
    if previous.get("checkedOn") == today:
        return max(1, before)
    return before + 1


def _station_key(prefecture, name):
    """Join by prefecture and a *conservative* normalized station name."""
    value = unicodedata.normalize("NFKC", name or "")
    value = re.sub(r"^道の駅\s*", "", value)
    value = re.sub(r"[\s・･_‐‑–—－-]+", "", value)
    return (prefecture or "", value)


def parse_app_station_master(source):
    """Read the app's existing JSON assignment without executing JavaScript.

    This is the APP snapshot, not a verified live MLIT station registry.
    """
    marker = "window.APP_DATA="
    i = source.find(marker)
    if i < 0:
        raise ValueError("APP_DATA JSON assignment not found")
    data, _ = json.JSONDecoder().raw_decode(source[i + len(marker):].lstrip())
    roads = data.get("roads")
    if not isinstance(roads, list) or not roads:
        raise ValueError("APP_DATA roads are missing")
    meta = data.get("meta", {})
    declared = meta.get("roadStations")
    if declared is not None and declared != len(roads):
        raise ValueError("APP_DATA station-count mismatch")
    seen_ids = set()
    stations = []
    for item in roads:
        code = item.get("id", "")
        name, pref = item.get("name", ""), item.get("prefecture", "")
        if not code or not name or not pref or code in seen_ids:
            raise ValueError("APP_DATA station identity missing or duplicated")
        seen_ids.add(code)
        stations.append({"id": code, "prefecture": pref, "roadName": name})
    return {"generated": meta.get("generated", ""),
            "version": meta.get("appVersion", ""),
            "stations": stations}


def make_report(discovery, registry, coverage, quality, regional, previous=None,
                today=None, station_master=None):
    today = today or datetime.now(JST).date().isoformat()
    previous = previous or {}
    fresh_discovery = discovery.get("checkedOn") == today
    configs = {x["id"]: x for x in registry.get("sources", [])
               if x.get("enabled", False)}
    earlier = {x["id"]: x for x in previous.get("sources", [])
               if x.get("id")}
    checked_sources, warnings, queue = [], [], []
    reason_totals = Counter()
    seen_candidates = set()

    for source in discovery.get("sources", []):
        sid = source.get("id", "")
        cfg = configs.get(sid)
        if cfg is None:
            warnings.append({"kind": "unknown_discovery_source", "sourceId": sid,
                             "severity": "warning"})
            continue
        former = earlier.get(sid, {})
        candidate_count = _positive_int(source.get("candidates"))
        examined = _positive_int(source.get("checked"))
        known = _positive_int(source.get("knownSkipped"))
        fetch_failures = _positive_int(source.get("fetchFailed"))
        listing_error = str(source.get("listingError") or "")
        error_now = bool(listing_error) or fetch_failures > 0
        zero_now = candidate_count == 0 and not error_now
        failure_streak = _day_streak(former, "failureDayStreak", error_now, today)
        empty_streak = _day_streak(former, "emptyCandidateDayStreak", zero_now, today)
        limit = _positive_int(cfg.get("maxArticles", 6))
        capped = (candidate_count > examined + known and examined >= limit)
        condition = ("source_error" if error_now else
                     "no_candidates" if zero_now else
                     "review_candidates" if source.get("reasons") else "active")
        item = {
            "id": sid, "prefecture": cfg["prefecture"],
            "roadName": cfg["roadName"],
            "url": cfg["listingUrl"],
            "checkedOn": today, "status": condition,
            "candidateCount": candidate_count, "checkedCount": examined,
            "acceptedCount": _positive_int(source.get("accepted")),
            "reconfirmedCount": _positive_int(source.get("reconfirmed")),
            "knownSkippedCount": known, "fetchFailedCount": fetch_failures,
            "listingError": listing_error[:200],
            "fetchErrors": (source.get("fetchErrors") or [])[:3],
            "failureDayStreak": failure_streak,
            "emptyCandidateDayStreak": empty_streak,
            "mayHaveUnreviewedCandidates": bool(capped),
        }
        checked_sources.append(item)
        if error_now:
            warnings.append({"kind": "source_fetch_error", "sourceId": sid,
                             "prefecture": cfg["prefecture"], "severity": "warning",
                             "failureDayStreak": failure_streak})
        elif empty_streak >= 3:
            warnings.append({"kind": "repeatedly_empty_listing", "sourceId": sid,
                             "prefecture": cfg["prefecture"], "severity": "notice",
                             "emptyCandidateDayStreak": empty_streak})
        if capped:
            warnings.append({"kind": "article_check_limit", "sourceId": sid,
                             "prefecture": cfg["prefecture"], "severity": "notice",
                             "candidateCount": candidate_count, "checkedCount": examined})
        for name, count in (source.get("reasons") or {}).items():
            reason_totals[name] += _positive_int(count)
        for example in source.get("rejectedExamples") or []:
            reason = example.get("reason", "")
            if reason in REVIEW_REASONS:
                kind, level = REVIEW_REASONS[reason]
            elif reason == "not_event" and any(
                    word in (example.get("title") or "") for word in CALENDAR_TERMS):
                kind, level = "calendar_announcement_needs_detail", "medium"
            else:
                continue
            url = example.get("url", "")
            if not url.startswith("https://"):
                continue
            key = (sid, url, kind)
            if key in seen_candidates:
                continue
            seen_candidates.add(key)
            queue.append({
                "sourceId": sid, "prefecture": cfg["prefecture"],
                "roadName": cfg["roadName"], "url": url,
                "title": (example.get("title") or "")[:190],
                "sourceReason": reason, "reviewReason": kind,
                "priority": level, "status": "unverified_candidate",
            })

    if not fresh_discovery:
        warnings.append({"kind": "stale_discovery_audit", "severity": "warning",
                         "expectedDate": today,
                         "actualDate": discovery.get("checkedOn")})
    for sid, cfg in configs.items():
        if sid not in {s["id"] for s in checked_sources}:
            warnings.append({"kind": "configured_source_not_audited",
                             "sourceId": sid, "prefecture": cfg["prefecture"],
                             "severity": "warning"})

    regional_checks = []
    for region in regional.get("sources", []):
        region_status = {
            "region": region.get("region", ""),
            "mode": region.get("status", ""),
            "homepageReachable": region.get("reachable"),
            "homepageCandidateCount": _positive_int(region.get("candidateCount")),
            "note": "Regional homepage status does NOT prove that its stations' events were parsed.",
        }
        regional_checks.append(region_status)
        if region.get("reachable") is False:
            warnings.append({"kind": "regional_homepage_unreachable",
                             "region": region_status["region"], "severity": "warning"})

    current_stations = {(x.get("prefecture"), station)
                        for x in coverage.get("prefectures", [])
                        for station in x.get("observedStations", [])}
    targeted_stations = {(x.get("prefecture"), station)
                         for x in coverage.get("prefectures", [])
                         for station in x.get("targetedStationFeeds", [])}
    published_without_target = sorted(current_stations - targeted_stations)
    inventory_rows, inventory_prefectures = [], []
    unmatched_target_names = []
    if station_master is not None:
        master_keys = {_station_key(x["prefecture"], x["roadName"])
                       for x in station_master["stations"]}
        normalized_targets = {_station_key(p, n) for p, n in targeted_stations}
        normalized_published = {_station_key(p, n) for p, n in current_stations}
        unmatched_target_names = [
            {"prefecture": p, "roadName": n}
            for p, n in sorted(targeted_stations)
            if _station_key(p, n) not in master_keys
        ]
        for station in station_master["stations"]:
            key = _station_key(station["prefecture"], station["roadName"])
            has_target = key in normalized_targets
            has_event = key in normalized_published
            inventory_rows.append({
                **station,
                "dedicatedSourceConfigured": has_target,
                "currentlyPublishedEvent": has_event,
                "status": ("dedicated_source_configured" if has_target else
                           "published_by_other_collectors" if has_event else
                           "no_dedicated_source"),
            })
        all_prefs = sorted(set(x["prefecture"] for x in inventory_rows))
        for pref in all_prefs:
            rows = [x for x in inventory_rows if x["prefecture"] == pref]
            inventory_prefectures.append({
                "prefecture": pref, "masterStations": len(rows),
                "dedicatedSources": sum(x["dedicatedSourceConfigured"] for x in rows),
                "publishedStations": sum(x["currentlyPublishedEvent"] for x in rows),
                "noDedicatedSource": sum(not x["dedicatedSourceConfigured"] for x in rows),
            })
    queue.sort(key=lambda x: (x["priority"] != "high",
                              x["prefecture"], x["sourceId"], x["url"]))
    uncovered = list(coverage.get("historical", {}).get(
        "previouslyObservedWithoutCurrentEvents", []))
    unconfirmed = [{
        "roadName": item.get("roadName", ""),
        "title": item.get("title", ""),
        "url": item.get("url", ""),
        "startDate": item.get("startDate", ""),
        "endDate": item.get("endDate", ""),
        "status": "needs_reconfirmation",
    } for item in quality.get("notReconfirmed", [])]
    alert_kinds = Counter(w["kind"] for w in warnings)
    return {
        "schemaVersion": 1,
        "checkedOn": today,
        "limitations": {
            "stationCoverage": ("Station counts use the app's dated APP_DATA snapshot, not a certified up-to-date official registry. No dedicated station source does not mean no regional coverage."
                                if station_master is not None else
                                "No complete nationwide station master is connected. Only configured feeds and already published stations are counted."),
            "eventRecall": "Actual event recall or missed-event percentage is unknown without an independently audited ground-truth sample.",
            "reviewQueue": "Samples of rejected articles only (source audit caps examples); not all rejected articles are real events.",
            "homepage": "Successful regional homepage access does not prove all regional station events were inspected.",
        },
        "summary": {
            "historicalPrefecturesReached": coverage.get("summary", {}).get("historicalObservedPrefectures", 0),
            "prefecturesWithCurrentEvents": coverage.get("summary", {}).get("observedPrefectures", 0),
            "currentEvents": coverage.get("summary", {}).get("registeredEvents", 0),
            "phase2SourcesConfigured": len(configs),
            "phase2SourcesAudited": len(checked_sources),
            "phase2AuditFresh": fresh_discovery,
            "regionalHomepagesAudited": len(regional_checks),
            "targetedStationPrefectures": coverage.get("summary", {}).get("targetedStationFeedPrefectures", 0),
            "publishedStations": len(current_stations),
            "publishedStationsWithoutDirectTarget": len(published_without_target),
            "appMasterStations": len(inventory_rows) if station_master is not None else None,
            "appMasterWithDedicatedSource": sum(x["dedicatedSourceConfigured"]
                                                for x in inventory_rows) if station_master is not None else None,
            "appMasterWithoutDedicatedSource": sum(not x["dedicatedSourceConfigured"]
                                                   for x in inventory_rows) if station_master is not None else None,
            "appMasterCurrentlyPublishedStations": sum(x["currentlyPublishedEvent"]
                                                        for x in inventory_rows) if station_master is not None else None,
            "configuredTargetNamesNotMatchedToAppMaster": len(unmatched_target_names),
            "potentialReviewSamples": len(queue),
            "rejectedReasonCounts": dict(sorted(reason_totals.items())),
            "sourcesWithFetchProblems": sum(s["status"] == "source_error" for s in checked_sources),
            "sourcesWithZeroCandidates": sum(s["status"] == "no_candidates" for s in checked_sources),
            "sourcesAtCheckLimit": sum(s["mayHaveUnreviewedCandidates"] for s in checked_sources),
            "warnings": len(warnings),
            "warningKinds": dict(sorted(alert_kinds.items())),
            "unreconfirmedEvents": len(unconfirmed),
        },
        "publishedStationsWithoutDirectTarget": [
            {"prefecture": pref, "roadName": station,
             "status": "published_through_other_collector_not_unmonitored"}
            for pref, station in published_without_target
        ],
        "appStationMaster": ({
            "version": station_master.get("version", ""),
            "generated": station_master.get("generated", ""),
            "source": "data/app_data.js",
        } if station_master is not None else None),
        "appMasterStations": inventory_rows,
        "appMasterPrefectures": inventory_prefectures,
        "configuredTargetsNotMatchedToAppMaster": unmatched_target_names,
        "historicallyReachedWithNoCurrentEvents": uncovered,
        "reviewCandidates": queue[:120],
        "unreconfirmedEvents": unconfirmed,
        "warnings": warnings,
        "sources": checked_sources,
        "regionalHomepages": regional_checks,
    }


def _md(value):
    return str(value or "").replace("|", r"\|").replace("\n", " ").replace("\r", " ").replace("\x60", "'")[:210]


def render_dashboard(report):
    """Small human-readable action list, deliberately labelled advisory."""
    summary = report["summary"]
    lines = [
        "# 道の駅イベント・取りこぼし監視ダッシュボード",
        "",
        "監査日（日本時間）: **" + report["checkedOn"] + "**",
        "",
        "> **注意:** このページは収集漏れの「可能性」を探すための監査です。",
        "> 未登録イベント数や全国の収集率を推定したものではありません。",
        "> 候補は未検証であり、公式日時・会場確認前に公開登録しません。",
        "",
        "## 収集状況",
        "",
        "| 指標 | 件数 |",
        "|---|---:|",
        "| 累計で収集実績のある都道府県 | {}/47 |".format(
            summary["historicalPrefecturesReached"]),
        "| 現在イベントのある都道府県 | {}/47 |".format(
            summary["prefecturesWithCurrentEvents"]),
        "| 現在の公開イベント | {} |".format(summary["currentEvents"]),
        "| 設定型の公式収集ルート（監査済/設定） | {}/{} |".format(
            summary["phase2SourcesAudited"], summary["phase2SourcesConfigured"]),
        "| 収集先の取得問題 | {} |".format(summary["sourcesWithFetchProblems"]),
        "| 候補が0件の収集先 | {} |".format(summary["sourcesWithZeroCandidates"]),
        "| 記事チェック上限に達した収集先 | {} |".format(
            summary["sourcesAtCheckLimit"]),
        "| 記事の要確認サンプル | {} |".format(summary["potentialReviewSamples"]),
        "| 既存イベントの未再確認 | {} |".format(summary["unreconfirmedEvents"]),
        "",
        "設定型監査データの鮮度: **{}**".format(
            "当日分" if summary["phase2AuditFresh"] else "古いか日付不明（要確認）"),
        "",
        "## 取得状況の注意事項",
        "",
    ]
    if not report["warnings"]:
        lines.append("現在の設定型監査で警告はありません（収集漏れがないという意味ではありません）。")
    for item in report["warnings"][:30]:
        target = item.get("sourceId") or item.get("region") or "監査全体"
        lines.append("- **{}** — {} （{}）".format(
            _md(item["kind"]), _md(target), _md(item["severity"])))
    if len(report["warnings"]) > 30:
        lines.append("- その他 {}件（全件はJSON参照）".format(
            len(report["warnings"]) - 30))
    lines += [
        "",
        "## 人が確認する候補（抜粋）",
        "",
        "以下は**不採用記事のサンプル**です。実際にイベントかどうかは未確認。",
        "",
        "| 県 | 駅 | 見出し | 保留理由 |",
        "|---|---|---|---|",
    ]
    for entry in report["reviewCandidates"][:25]:
        lines.append("| {} | {} | {} | {} |".format(
            _md(entry["prefecture"]), _md(entry["roadName"]),
            _md(entry["title"]), _md(entry["reviewReason"])))
    if not report["reviewCandidates"]:
        lines.append("| ― | ― | 現在のサンプルなし | ― |")
    lines += [
        "",
        "## 収集先について",
        "",
        "- **現在登録されている駅数:** {}駅".format(summary["publishedStations"]),
        "- **個別対象駅として設定されていない登録済み駅:** {}駅".format(
            summary["publishedStationsWithoutDirectTarget"]),
        "  - 地域サイト等で登録されている場合があるため、「未監視駅」とは断定できません。",
        "- **全国すべての道の駅との照合:** 未実施（完全な駅マスタ未接続）。",
        "- **現行イベント0件だが過去の登録実績がある県:** " +
        ("、".join(report["historicallyReachedWithNoCurrentEvents"]) or "なし"),
        "",
        "詳細データ: [収集漏れ監査JSON](../data/road_event_gap_monitor.json)、"
        "[県別収集監査JSON](../data/prefecture_event_coverage.json)",
        "",
    ]
    return "\n".join(lines)


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _load_master():
    return parse_app_station_master((DATA / "app_data.js").read_text(encoding="utf-8"))


def main():
    old = _load(OUTPUT.name) if OUTPUT.exists() else {}
    report = make_report(
        _load("station_event_discovery_audit.json"),
        _load("station_event_discovery_sources.json"),
        _load("prefecture_event_coverage.json"),
        _load("road_event_quality_report.json"),
        _load("road_event_sources_report.json"),
        previous=old, station_master=_load_master())
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
        OUTPUT.write_text(rendered, encoding="utf-8")
    dashboard = DATA.parent / "docs" / "ROAD_EVENT_GAP_DASHBOARD.md"
    content = render_dashboard(report)
    if not dashboard.exists() or dashboard.read_text(encoding="utf-8") != content:
        dashboard.write_text(content, encoding="utf-8")
    s = report["summary"]
    print("収集漏れ監査: 設定型 {}/{}先 / 要確認候補サンプル {}件 / "
          "取得問題 {}先 / 候補0 {}先 / 検査上限 {}先 / 未再確認 {}件".format(
              s["phase2SourcesAudited"], s["phase2SourcesConfigured"],
              s["potentialReviewSamples"], s["sourcesWithFetchProblems"],
              s["sourcesWithZeroCandidates"], s["sourcesAtCheckLimit"],
              s["unreconfirmedEvents"]))
    # Surface genuine source-fetch and audit-freshness problems even if the
    # collector finishes green. These are advisory, not fake event records.
    for warning in report["warnings"]:
        if warning["kind"] in ("source_fetch_error", "stale_discovery_audit",
                               "configured_source_not_audited",
                               "regional_homepage_unreachable"):
            target = warning.get("sourceId") or warning.get("region") or "audit"
            print("::warning title=Road event source monitor::{}: {}".format(
                warning["kind"], target))
    # Warning findings must not fail the collection pipeline. Invalid
    # input/schema or code errors should still raise to make failure visible.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

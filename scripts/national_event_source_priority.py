"""Nationwide-first event-source planning, based only on existing audit evidence.

No scraping, publishing, or traffic ranking occurs here. Homepage reachability
is never treated as verified event coverage. Keep the 1234-station URL sweep.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = DATA / "national_event_source_priority.json"
DASHBOARD = ROOT / "docs" / "NATIONAL_EVENT_PRIORITY_DASHBOARD.md"

def make_report(coverage, source_audit):
    regions = {s["region"]: s for s in source_audit.get("sources", [])}
    result = []
    region_prefectures = {}
    for p in coverage.get("prefectures", []):
        region_prefectures.setdefault(p.get("reportingRegion"), []).append(p)
    for region in coverage.get("regions", []):
        name = region["region"]
        audit = regions.get(name, {})
        gaps = region.get("zeroRegisteredPrefectures", [])
        adapter = audit.get("status") == "adapter"
        reachable = audit.get("reachable") is True
        if not reachable:
            next_action = "repair_regional_source_or_verify_alternative"
        elif not adapter:
            next_action = "verify_event_listing_and_build_safe_adapter"
        elif gaps:
            next_action = "audit_station_matching_and_missing_prefectures"
        else:
            next_action = "maintain_and_expand_existing_adapter"
        secondary = audit.get("curatedEventListing", {})
        prefectures = region_prefectures.get(name, [])
        result.append({
            "region": name,
            "prefectureCount": region["prefectureCount"],
            "prefecturesWithoutCurrentPublishedEvents": gaps,
            "currentPublishedEventCount": region["registeredEventCount"],
            "officialSourceUrl": audit.get("url", ""),
            "sourceAuditState": "reachable" if reachable else "unreachable_or_unknown",
            "existingSourceMode": audit.get("status", "unknown"),
            "listingCandidatesSeen": audit.get("candidateCount", 0),
            "secondaryListingState": secondary.get("state", "not_configured"),
            "secondaryListingCandidates": secondary.get("candidateCount", 0),
            "prefectureEvidence": [{
                "prefecture": p["prefecture"],
                "currentPublishedEvents": p.get("eventCount", 0),
                "targetedStationFeedCount": len(p.get("targetedStationFeeds", [])),
                "regionalHomepageReachable": p.get("regionalHomepageReachable", False),
                "evidenceLevel": ("published_events_observed" if p.get("eventCount", 0) > 0
                    else "targeted_feed_configured_no_current_publication"
                    if p.get("targetedStationFeeds") else "regional_homepage_only_or_unknown"),
            } for p in prefectures],
            "note": "Source audit candidates are not verified station events.",
            "nextAction": next_action,
        })
    # Nationwide reach first, then evidence-backed high-traffic station work.
    rank = {"repair_regional_source_or_verify_alternative": 0,
            "verify_event_listing_and_build_safe_adapter": 1,
            "audit_station_matching_and_missing_prefectures": 2,
            "maintain_and_expand_existing_adapter": 3}
    result.sort(key=lambda x: (rank[x["nextAction"]], -len(x["prefecturesWithoutCurrentPublishedEvents"]), x["region"]))
    return {
        "schemaVersion": 1, "strategy": ["nationwide_official_source_coverage",
                                        "verified_high_traffic_stations",
                                        "remaining_individual_stations"],
        "auditEvidenceDate": coverage.get("basisUpdatedAt", ""),
        "regionAuditCount": len(result),
        "prefectureEvidenceCount": sum(len(x["prefectureEvidence"]) for x in result),
        "publishedPrefectureCount": coverage["summary"]["observedPrefectures"],
        "prefecturesWithNoCurrentPublishedEvents": coverage["summary"]["zeroRegisteredPrefectures"],
        "regions": result,
        "highTrafficStationPriority": {"state": "awaiting_objective_visitation_evidence",
            "rule": "Do not rank stations using intuition or current event count."},
        "interpretation": "Current event count is not source recall; no events published does not mean no event exists.",
    }

def format_dashboard(report):
    lines = ["# 全国優先・道の駅イベント収集 改善台帳", "",
        "全国公式ソースを優先し、次に来場者等の根拠がある高稼働駅、最後に全個別駅を補完する。", "",
        "現行イベント登録のない県も、未監視・イベント無しとは判定しない。", "",
        "| 地域 | 現行公開件数 | 現行0件の県 | 広域サイト監査 | 次の改善 |",
        "|---|---:|---|---|---|"]
    for r in report["regions"]:
        lines.append("| {region} | {currentPublishedEventCount} | {gap} | {mode} / {reach} | {nextAction} |".format(
            **r, gap="、".join(r["prefecturesWithoutCurrentPublishedEvents"]) or "なし",
            mode=r["existingSourceMode"], reach=r["sourceAuditState"]))
    lines += ["", "## 47都道府県の収集根拠", "",
              "| 都道府県 | 現行公開イベント | 個別設定数 | 判断できる範囲 |",
              "|---|---:|---:|---|"]
    for r in report["regions"]:
        for p in r["prefectureEvidence"]:
            lines.append("| {prefecture} | {currentPublishedEvents} | {targetedStationFeedCount} | {evidenceLevel} |".format(**p))
    lines += ["", "※広域サイトに接続できたことは、イベントを抽出・公開できた証明ではない。",
              "※人気駅の優先順位は、客観的な利用・来場者データを確認後に別途付与する。",
              "※既存のイベント公開判定・重複除去・日付／駅構内会場の照合は変更しない。", ""]
    return "\n".join(lines)

def main():
    coverage = json.loads((DATA / "prefecture_event_coverage.json").read_text(encoding="utf-8"))
    audit = json.loads((DATA / "road_event_sources_report.json").read_text(encoding="utf-8"))
    report = make_report(coverage, audit)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    dashboard = format_dashboard(report)
    for path, content in ((OUTPUT, output), (DASHBOARD, dashboard)):
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
    print("Nationwide priority dashboard: {} regions / {} prefectures without current published events".format(
        len(report["regions"]), report["prefecturesWithNoCurrentPublishedEvents"]))

if __name__ == "__main__":
    main()

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
            "regionalAuditError": audit.get("error", ""),
            "secondaryAuditError": secondary.get("error", ""),
            "regionalArticleChecked": None,
            "regionalArticleAccepted": None,
            "prefectureEvidence": [{
                "prefecture": p["prefecture"],
                "currentPublishedEvents": p.get("eventCount", 0),
                "targetedStationFeedCount": len(p.get("targetedStationFeeds", [])),
                "configuredSourcesAudited": 0,
                "candidateArticles": 0,
                "articlesAcceptedByDiscovery": 0,
                "sourcesWithFetchProblems": 0,
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


def attach_station_source_health(report, discovery):
    """Join the latest per-station audit without inventing per-source timestamps.

    checkedOn is the date of the whole audit. It is not a historical
    'last successful fetch' unless this snapshot reports a successful fetch.
    Regional source reachability remains independent.
    """
    by_pref = {}
    for row in discovery.get("sources", []):
        pref = row.get("prefecture")
        if not pref:
            continue
        data = by_pref.setdefault(pref, {"configuredSourcesAudited": 0,
            "sourcesWithFetchProblems": 0, "sourcesWithSuccessfulListing": 0,
            "candidateArticles": 0, "articlesChecked": 0,
            "articlesAcceptedByDiscovery": 0, "articlesUnverified": 0})
        data["configuredSourcesAudited"] += 1
        count = lambda field: max(0, int(row.get(field, 0) or 0))
        candidates = count("candidates")
        inspected = count("checked")
        accepted = count("accepted")
        data["candidateArticles"] += candidates
        data["articlesChecked"] += inspected
        data["articlesAcceptedByDiscovery"] += accepted
        data["articlesUnverified"] += max(0, candidates - inspected - count("knownSkipped"))
        trouble = bool(row.get("listingError")) or count("fetchFailed") > 0
        if trouble:
            data["sourcesWithFetchProblems"] += 1
        if not row.get("listingError"):
            data["sourcesWithSuccessfulListing"] += 1
    for region in report["regions"]:
        for pref in region["prefectureEvidence"]:
            stats = by_pref.get(pref["prefecture"], {})
            pref["dedicatedSourceLatestAuditDate"] = discovery.get("checkedOn", "") if stats else ""
            for key in ("configuredSourcesAudited", "sourcesWithFetchProblems",
                        "sourcesWithSuccessfulListing", "candidateArticles",
                        "articlesChecked", "articlesAcceptedByDiscovery",
                        "articlesUnverified"):
                pref[key] = stats.get(key, 0)
            pref["sourceHealthEvidence"] = "audited_dedicated_sources" if stats else "no_dedicated_audit"
    report["stationSourceAuditDate"] = discovery.get("checkedOn", "")
    report["stationSourcesAudited"] = sum(v["configuredSourcesAudited"] for v in by_pref.values())
    return report

def attach_regional_adapter_health(report, audits):
    """Adapter metrics are distinct from regional link-discovery candidates."""
    lookup = {r["region"]: r for r in report["regions"]}
    hok = audits.get("北陸", {})
    pages = hok.get("pages", [])
    if "北陸" in lookup:
        lookup["北陸"]["adapterAudit"] = {
            "auditedPages": len(pages),
            "candidateMatches": sum(p.get("staticMatched", 0) + p.get("browserMatched", 0) for p in pages),
            "fetchProblems": sum(bool(p.get("browserError")) for p in pages),
            "acceptedByAdapter": hok.get("accepted", hok.get("eventCount")),
            "duplicateCards": hok.get("duplicateCards"),
            "browserRenderedPages": hok.get("browserRenderedPages"),
            "browserFailedPages": hok.get("browserFailedPages"),
            "staticFetchFailedPages": hok.get("staticFetchFailedPages"),
        }
    kyu = audits.get("九州・沖縄", {})
    if "九州・沖縄" in lookup:
        sources = kyu.get("sources", [])
        lookup["九州・沖縄"]["adapterAudit"] = {
            "auditedSources": len(sources),
            "candidateMatches": sum(p.get("candidates", 0) for p in sources),
            "fetchProblems": sum(bool(p.get("error")) or p.get("failed", 0) > 0 for p in sources),
            "acceptedByAdapter": kyu.get("accepted"),
            "articleChecked": sum(x.get("checked", 0) for x in sources),
            "rejectionReasons": {k: sum(x.get(k, 0) for x in sources) for k in ("missingPublication", "missingEventDate", "past", "failed")},
        }
    kan = audits.get("関東", {})
    if "関東" in lookup and kan:
        lookup["関東"]["adapterAudit"] = {
            "candidateMatches": kan.get("candidateCount", 0),
            "acceptedByAdapter": kan.get("acceptedByAdapter"),
            "articleFetchSucceeded": kan.get("articleFetchSucceeded"),
            "articleFetchFailed": kan.get("articleFetchFailed"),
            "articleChecked": sum(1 for d in kan.get("decisions", []) if d.get("reason") not in ("station_unmatched",)),
            "rejectionReasons": {reason: sum(1 for d in kan.get("decisions", []) if d.get("reason") == reason)
                                 for reason in set(d.get("reason") for d in kan.get("decisions", []))},
        }
    kin = audits.get("近畿", {})
    if "近畿" in lookup and "sources" in kin:
        sources = kin["sources"]
        lookup["近畿"]["adapterAudit"] = {
            "auditedSources": len(sources),
            "candidateMatches": sum(x.get("candidates", 0) for x in sources),
            "articleChecked": sum(x.get("checked", 0) for x in sources),
            "acceptedByAdapter": kin.get("accepted"),
            "fetchProblems": sum(bool(x.get("listingError")) or x.get("failed", 0) > 0 for x in sources),
            "rejectionReasons": {key: sum(x.get(key, 0) for x in sources)
                                 for key in ("past", "undated", "venueMismatch", "failed")},
        }
    chubu = audits.get("中部", {})
    if "中部" in lookup and "pages" in chubu:
        pages = chubu["pages"]
        lookup["中部"]["adapterAudit"] = {
            "auditedPages": len(pages),
            "datedPdfRows": sum(len(x.get("dated_rows", [])) for x in pages),
            "candidateMatches": None,
            "articleChecked": None,
            "acceptedByAdapter": None,
            "fetchProblems": None,
            "auditEvidence": "pdf_layout_only",
        }
    return report

def standardize_nine_region_audits(report):
    """One honest schema for every region; unknown metrics stay null."""
    for row in report["regions"]:
        a = row.get("adapterAudit", {})
        region = row["region"]
        row["collectionHealth"] = {
            "homepageReachable": row["sourceAuditState"] == "reachable",
            "homepageCandidateLinks": row.get("listingCandidatesSeen", 0),
            "secondaryListingState": row.get("secondaryListingState", "not_configured"),
            "secondaryCandidateLinks": row.get("secondaryListingCandidates", 0),
            "adapterCandidates": a.get("candidateMatches"),
            "adapterAccepted": a.get("acceptedByAdapter"),
            "adapterFetchProblems": a.get("fetchProblems"),
            "publishedEventsInRegion": row["currentPublishedEventCount"],
            "articleChecked": a.get("articleChecked"),
            "lastSuccessfulCollectionAt": None,
            "rejectionReasons": a.get("rejectionReasons"),
            "articleFetchSucceeded": a.get("articleFetchSucceeded"),
            "articleFetchFailed": a.get("articleFetchFailed"),
            "browserRenderedPages": a.get("browserRenderedPages"),
            "browserFailedPages": a.get("browserFailedPages"),
            "duplicateCards": a.get("duplicateCards"),
            "datedPdfRows": a.get("datedPdfRows"),
            "auditEvidence": ("adapter_audit_available" if a else "regional_links_only"),
            "region": region,
        }
    return report

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
    lines += ["", "## 広域サイト監査結果", "",
              "| 地域 | サイト候補 | 追加一覧状態 | 追加候補 | エラー |",
              "|---|---:|---|---:|---|"]
    for r in report["regions"]:
        lines.append("| {} | {} | {} | {} | {} |".format(
            r["region"], r["listingCandidatesSeen"], r["secondaryListingState"],
            r["secondaryListingCandidates"], r["regionalAuditError"] or r["secondaryAuditError"] or "なし"))
    lines += ["", "## 広域アダプター実績（監査データのある地域のみ）", "",
              "| 地域 | 候補・検出件数 | 記事確認 | 収集器採用 | 取得障害元・頁 |",
              "|---|---:|---:|---:|---:|"]
    for r in report["regions"]:
        a = r.get("adapterAudit")
        if a:
            lines.append("| {} | {} | {} | {} | {} |".format(r["region"],
                a.get("candidateMatches", "不明"), a.get("articleChecked", "不明"),
                a.get("acceptedByAdapter", "不明"), a.get("fetchProblems", "不明")))
    lines += ["", "※47県均等化の比較には各地域の collectionHealth を用いる。未計測の指標は null（不明）。",
              "※北陸の検出件数は走査ページ間で重複する場合がある。収集器採用は最終公開件数ではない。",
              "※広域サイトの候補数は検証済みイベント数ではない。", "", "## 47都道府県の収集根拠", "",
              "| 都道府県 | 公開件数 | 設定数 | 個別監査元 | 記事候補 | 記事採用 | 取得障害元 | 根拠 |",
              "|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in report["regions"]:
        for p in r["prefectureEvidence"]:
            lines.append("| {prefecture} | {currentPublishedEvents} | {targetedStationFeedCount} | {configuredSourcesAudited} | {candidateArticles} | {articlesAcceptedByDiscovery} | {sourcesWithFetchProblems} | {evidenceLevel} |".format(**p))
    lines += ["", "※記事採用数は個別収集器の監査値であり、アプリの最終公開件数とは異なる。",
              "※監査日付は最新監査日のみを表し、最終成功日時の履歴ではない。",
              "※広域サイトに接続できたことは、イベントを抽出・公開できた証明ではない。",
              "※人気駅の優先順位は、客観的な利用・来場者データを確認後に別途付与する。",
              "※既存のイベント公開判定・重複除去・日付／駅構内会場の照合は変更しない。", ""]
    return "\n".join(lines)

def main():
    coverage = json.loads((DATA / "prefecture_event_coverage.json").read_text(encoding="utf-8"))
    audit = json.loads((DATA / "road_event_sources_report.json").read_text(encoding="utf-8"))
    report = make_report(coverage, audit)
    discovery_path = DATA / "station_event_discovery_audit.json"
    discovery = json.loads(discovery_path.read_text(encoding="utf-8")) if discovery_path.exists() else {}
    report = attach_station_source_health(report, discovery)
    audits = {}
    for region, filename in (("北陸", "hokuriku_event_audit.json"),
                             ("九州・沖縄", "kyushu_okinawa_event_audit.json"),
                             ("関東", "kanto_association_event_audit.json"),
                             ("近畿", "kinki_five_prefectures_audit.json"),
                             ("中部", "chubu_event_layout_report.json")):
        path = DATA / filename
        if path.exists():
            audits[region] = json.loads(path.read_text(encoding="utf-8"))
    report = attach_regional_adapter_health(report, audits)
    report = standardize_nine_region_audits(report)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    dashboard = format_dashboard(report)
    for path, content in ((OUTPUT, output), (DASHBOARD, dashboard)):
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
    print("Nationwide priority dashboard: {} regions / {} prefectures without current published events".format(
        len(report["regions"]), report["prefecturesWithNoCurrentPublishedEvents"]))

if __name__ == "__main__":
    main()

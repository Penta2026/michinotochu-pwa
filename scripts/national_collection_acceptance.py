"""Validate nationwide road-event collection outputs without inventing coverage."""
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REGIONS = ("北海道", "東北", "関東", "北陸", "中部", "近畿", "中国", "四国", "九州・沖縄")
AUDITS = {
    "北海道": "hokkaido_event_audit.json",
    "東北": "tohoku_event_adapter_audit.json",
    "関東": "kanto_association_event_audit.json",
    "北陸": "hokuriku_event_audit.json",
    "中部": "chubu_event_layout_report.json",
    "近畿": "kinki_five_prefectures_audit.json",
    "中国": "chugoku_event_adapter_audit.json",
    "四国": "shikoku_event_adapter_audit.json",
    "九州・沖縄": "kyushu_okinawa_event_audit.json",
}
OUTPUT = DATA / "national_collection_acceptance.json"


def check(coverage, sources, priority, audit_files, checked_on):
    issues, warnings = [], []
    prefectures = coverage.get("prefectures", [])
    expected = set(REGIONS)
    actual = {r.get("region") for r in coverage.get("regions", [])}
    if len(prefectures) != 47 or len({p.get("prefecture") for p in prefectures}) != 47:
        issues.append("prefecture_master_not_47_unique")
    if actual != expected or len(coverage.get("regions", [])) != 9:
        issues.append("coverage_regions_not_nine")
    home = {r.get("region"): r for r in sources.get("sources", [])}
    if len(home) != 9 or not expected.issubset(home):
        issues.append("regional_source_audit_missing_regions")
    pri = priority.get("regions", [])
    if {r.get("region") for r in pri} != expected or len(pri) != 9:
        issues.append("priority_regions_not_nine")
    total = sum(p.get("eventCount", 0) for p in prefectures)
    if total != coverage.get("summary", {}).get("registeredEvents"):
        issues.append("published_event_count_mismatch")
    empty = sorted(p["prefecture"] for p in prefectures if p.get("eventCount", 0) == 0)
    if len(empty) != coverage.get("summary", {}).get("zeroRegisteredPrefectures"):
        issues.append("zero_prefecture_count_mismatch")
    status = []
    for region in REGIONS:
        info = home.get(region, {})
        filename = AUDITS[region]
        recorded = audit_files.get(filename)
        if recorded is None:
            warnings.append("missing_adapter_audit:" + region)
        elif "schemaVersion" not in recorded:
            warnings.append("unversioned_adapter_audit:" + region)
        elif recorded.get("checkedOn") and recorded["checkedOn"] != checked_on:
            warnings.append("stale_adapter_audit:" + region)
        if not info.get("reachable"):
            warnings.append("regional_homepage_unreachable:" + region)
        if recorded is not None and recorded.get("checkedOn") is None:
            warnings.append("adapter_audit_date_unknown:" + region)
        status.append({"region": region, "homepageReachable": info.get("reachable"),
                       "adapterAuditFile": filename, "adapterAuditPresent": recorded is not None,
                       "adapterAuditIsFresh": recorded.get("checkedOn") == checked_on
                           if recorded is not None and recorded.get("checkedOn") else None})
    return {"schemaVersion": 1, "checkedOn": checked_on,
            "structurallyValid": not issues, "blockingIssues": issues,
            "warnings": warnings, "regions": status,
            "publishedEvents": total, "publishedPrefectures": 47-len(empty),
            "prefecturesWithoutCurrentPublication": empty,
            "note": "Homepage reachability and audit presence do not prove article coverage or successful publication."}


def main():
    def load(name):
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    files = {}
    for filename in AUDITS.values():
        if (DATA / filename).exists():
            files[filename] = load(filename)
    result = check(load("prefecture_event_coverage.json"),
                   load("road_event_sources_report.json"),
                   load("national_event_source_priority.json"), files,
                   date.today().isoformat())
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != payload:
        OUTPUT.write_text(payload, encoding="utf-8")
    print("National collection acceptance: valid={}, warnings={}, published={}/47 prefectures".format(
        result["structurallyValid"], len(result["warnings"]), result["publishedPrefectures"]))
    if result["blockingIssues"]:
        raise SystemExit("Nationwide structural audit failed: " + ", ".join(result["blockingIssues"]))


if __name__ == "__main__":
    main()

"""Phase 2: concrete evidence and blockers for every currently zero-publication prefecture."""
import json
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
OUTPUT = DATA / "zero_prefecture_action_report.json"


def build(coverage, discovery, leads):
    zero = [x for x in coverage["prefectures"] if x.get("eventCount") == 0]
    tracked = {x["prefecture"] for x in zero}
    entries = []
    for pref in zero:
        name = pref["prefecture"]
        sources = [s for s in discovery.get("sources", []) if s.get("prefecture") == name]
        evidence = [s for s in leads.get("sources", []) if s.get("prefecture") == name]
        candidates = sum(s.get("candidates", 0) for s in sources)
        inspected = sum(s.get("checked", 0) for s in sources)
        accepted = sum(s.get("accepted", 0) for s in sources)
        reasons = {}
        for source in sources:
            for reason, count in source.get("reasons", {}).items():
                reasons[reason] = reasons.get(reason, 0) + count
        entries.append({
            "prefecture": name, "region": pref.get("reportingRegion"),
            "currentEvents": 0, "configuredStationDiscoverySources": len(sources),
            "listingCandidates": candidates, "articlesChecked": inspected,
            "acceptedByDiscoveryAdapter": accepted,
            "uninspectedCandidates": sum(s.get("uninspectedCandidates", 0) for s in sources),
            "rejectionReasons": reasons,
            "officialLeadUrls": [x["url"] for x in evidence],
            "officialLeadCount": len(evidence),
            "nextAction": ("verify_existing_adapter_rejections" if sources
                           else "configure_and_verify_new_official_station_feed"),
            "sourceIds": [s["id"] for s in sources]
        })
    uncovered = sorted(tracked - {x["prefecture"] for x in leads.get("sources", [])})
    return {"schemaVersion": 1, "checkedOn": coverage.get("basisUpdatedAt"),
            "prefecturesWithoutCurrentEvents": len(zero),
            "prefecturesWithOfficialReviewLeads": len(tracked) - len(uncovered),
            "uncoveredPrefectures": uncovered, "prefectures": entries,
            "limitations": "Leads are NOT confirmed valid event records. Adapter acceptance is not final publication."}


def main():
    def load(path):
        return json.loads((DATA / path).read_text(encoding="utf-8"))
    report = build(load("prefecture_event_coverage.json"),
                   load("station_event_discovery_audit.json"),
                   load("zero_prefecture_official_leads.json"))
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(f"Zero-event prefecture review: {report['prefecturesWithoutCurrentEvents']} target / "
          f"{report['prefecturesWithOfficialReviewLeads']} with research leads")
    if report["uncoveredPrefectures"]:
        raise SystemExit("No official research leads: " + ", ".join(report["uncoveredPrefectures"]))


if __name__ == "__main__":
    main()

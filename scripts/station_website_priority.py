"""Rank the nationwide 1,234 station website leads without treating hints as verified feeds."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
OUTPUT = DATA / "station_website_priority.json"
PREFERRED = {"station_or_partner_site_unverified": 0, "municipal_information": 1, "regional_directory": 2}


def build(queue, zero_prefectures):
    rows = queue["stations"]
    ids = [r["id"] for r in rows]
    if len(rows) != 1234 or len(ids) != len(set(ids)):
        raise ValueError("Expected 1234 uniquely identified stations")
    urgent = set(zero_prefectures)
    candidates = []
    for station in rows:
        if station["directoryInspectionState"] != "checked":
            continue
        for hint in station.get("candidates", []):
            if hint.get("reviewStatus") != "awaiting_review" or hint.get("kind") not in PREFERRED:
                continue
            candidates.append({
                "stationId": station["id"],
                "prefecture": station["prefecture"], "roadName": station["roadName"],
                "url": hint["url"], "kind": hint["kind"],
                "reason": "zero_current_event_prefecture" if station["prefecture"] in urgent
                          else "unverified_official_website_hint",
                "verified": False,
            })
    candidates.sort(key=lambda x: (
        0 if x["prefecture"] in urgent else 1,
        PREFERRED[x["kind"]], x["prefecture"], x["stationId"], x["url"]))
    inspected = sum(s["directoryInspectionState"] == "checked" for s in rows)
    return {"schemaVersion": 1, "masterStations": len(rows),
            "directoryInspected": inspected, "directoryRemaining": len(rows)-inspected,
            "stationsWithUnverifiedCandidates": len({x["stationId"] for x in candidates}),
            "candidateUrlsAwaitingReview": len(candidates),
            "zeroCurrentEventPrefectureCandidates": sum(x["prefecture"] in urgent for x in candidates),
            "reviewPriority": candidates,
            "limitation": "Directory link hints are not verified station ownership, event listings or publishable events."}


def main():
    queue = json.loads((DATA / "station_website_review_queue.json").read_text(encoding="utf-8"))
    coverage = json.loads((DATA / "prefecture_event_coverage.json").read_text(encoding="utf-8"))
    zero = [p["prefecture"] for p in coverage["prefectures"] if p.get("eventCount") == 0]
    result = build(queue, zero)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != text:
        OUTPUT.write_text(text, encoding="utf-8")
    print("Station official URL review: {}/1234 directories, {} URL hints awaiting review".format(
        result["directoryInspected"], result["candidateUrlsAwaitingReview"]))


if __name__ == "__main__":
    main()

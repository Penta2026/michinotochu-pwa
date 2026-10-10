"""Conservative reconciliation and transparent audit for official event feeds."""
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "road_event_quality_report.json"

def canonical_title(value):
    s = unicodedata.normalize("NFKC", value or "").casefold()
    s = re.sub(r"^[●\s]+", "", s)
    s = re.sub(r"^[【\[]?(?:道の駅)?[^\]】]{1,35}[\]】]\s*", "", s)
    s = re.sub(r"\s+", "", s)
    return s

def identity(record):
    # Distinguish simultaneous events, including several entries in one PDF.
    return (record.get("url", ""), record.get("roadName", ""),
            canonical_title(record.get("title", "")))

def exact_key(record):
    return (record.get("url", ""), record.get("roadName", ""),
            record.get("title", ""), record.get("startDate", ""))

def plausible(record, today):
    try:
        first = date.fromisoformat(record["startDate"])
        last = date.fromisoformat(record["endDate"])
    except (KeyError, ValueError, TypeError):
        return False
    return first <= last and last >= today and bool(record.get("url") and record.get("roadName") and record.get("title"))

def reconcile(old, new, today):
    report = {"schemaVersion": 1, "inputPrevious": len(old), "inputCollected": len(new),
              "expiredOrInvalid": [], "corrected": [], "exactDuplicates": [],
              "possibleDuplicates": [], "finalCount": 0}
    preserved = []
    for event in old:
        if not plausible(event, today):
            report["expiredOrInvalid"].append({"roadName": event.get("roadName"), "title": event.get("title")})
            continue
        if "chubu-michinoeki.org/pdf/" in event.get("url", "") and re.match(r"^\s*●\s*[～〜~]", event.get("title", "")):
            report["expiredOrInvalid"].append({"roadName": event.get("roadName"), "title": event.get("title"), "reason": "unknown_start"})
            continue
        preserved.append(event)
    by_id = {identity(e): e for e in preserved}
    for event in new:
        if not plausible(event, today):
            report["expiredOrInvalid"].append({"roadName": event.get("roadName"), "title": event.get("title"), "reason": "invalid_new"})
            continue
        key = identity(event)
        prev = by_id.get(key)
        if prev is not None and (prev["startDate"], prev["endDate"]) != (event["startDate"], event["endDate"]):
            report["corrected"].append({"roadName": event["roadName"], "title": event["title"],
                "oldDates": [prev["startDate"], prev["endDate"]],
                "newDates": [event["startDate"], event["endDate"]]})
        by_id[key] = event
    # Cross-source possible duplicates: advisory only; never remove different
    # event names or records without a proven shared identifier.
    items = list(by_id.values())
    for i, one in enumerate(items):
        for other in items[i+1:]:
            if (one["roadName"] == other["roadName"] and one["startDate"] == other["startDate"]
                and one["url"] != other["url"] and canonical_title(one["title"]) == canonical_title(other["title"])):
                report["possibleDuplicates"].append({"roadName": one["roadName"],
                    "titles": [one["title"], other["title"]], "urls": [one["url"], other["url"]]})
    results = sorted(items, key=lambda e: (e["startDate"], e["roadName"], e["title"]))
    report["finalCount"] = len(results)
    return results, report

def write_report(report):
    # Stable JSON avoids daily commits for unchanged diagnostics.
    content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if not REPORT.exists() or REPORT.read_text(encoding="utf-8") != content:
        REPORT.write_text(content, encoding="utf-8")

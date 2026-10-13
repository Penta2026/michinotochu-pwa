"""Phase 5 nationwide checks on PUBLISHED events; conservative, advisory except hard structural failures."""
import json
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

DATA = Path(__file__).resolve().parents[1] / "data"
OUTPUT = DATA / "national_published_event_quality.json"


def audit(events, master, today):
    stations = {(r["prefecture"], r["name"]) for r in master}
    critical, review = [], []
    seen = set()
    for index, row in enumerate(events):
        ref = {"index": index, "prefecture": row.get("prefecture"),
               "station": row.get("roadName"), "title": row.get("title"),
               "url": row.get("url")}
        key = (row.get("prefecture"), row.get("roadName"), row.get("title"),
               row.get("startDate"), row.get("endDate"))
        if key in seen:
            critical.append({**ref, "reason": "exact_publication_duplicate"})
        seen.add(key)
        try:
            start = date.fromisoformat(row["startDate"])
            end = date.fromisoformat(row["endDate"])
        except (ValueError, TypeError, KeyError):
            critical.append({**ref, "reason": "invalid_date"})
            continue
        if end < start:
            critical.append({**ref, "reason": "reversed_dates"})
        if end < today:
            critical.append({**ref, "reason": "expired_event"})
        if (end-start).days > 120:
            review.append({**ref, "reason": "long_running_event_over_120_days"})
        parsed = urlsplit(row.get("url") or "")
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            critical.append({**ref, "reason": "unsafe_or_missing_official_link"})
        if (row.get("prefecture"), row.get("roadName")) not in stations:
            review.append({**ref, "reason": "station_identity_needs_review"})
        if not row.get("title"):
            critical.append({**ref, "reason": "missing_title"})
        if row.get("publishedAt"):
            try:
                if date.fromisoformat(row["publishedAt"]) > today:
                    review.append({**ref, "reason": "future_publication_timestamp"})
            except (TypeError, ValueError):
                review.append({**ref, "reason": "invalid_publication_timestamp"})
    return {"schemaVersion": 1, "checkedOn": today.isoformat(), "publishedCount": len(events),
            "criticalCount": len(critical), "manualReviewCount": len(review),
            "critical": critical, "review": review,
            "limits": "Cannot prove on-site venue, official ownership or current event status from metadata alone."}


def main():
    from station_coverage_registry import read_app_stations
    events = json.loads((DATA/"road_events.json").read_text(encoding="utf-8"))["events"]
    master = read_app_stations((DATA/"app_data.js").read_text(encoding="utf-8"))
    result = audit(events, master, date.today())
    content = json.dumps(result, ensure_ascii=False, indent=2)+"\n"
    if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != content:
        OUTPUT.write_text(content, encoding="utf-8")
    print("Nationwide published quality: {}, critical {}, review {}".format(
        len(events), result["criticalCount"], result["manualReviewCount"]))
    if result["criticalCount"]:
        raise SystemExit("Published event quality critical issues: "+str(result["criticalCount"]))


if __name__ == "__main__":
    main()

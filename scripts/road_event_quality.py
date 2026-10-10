"""Conservative reconciliation and transparent audit for official event feeds."""
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "road_event_quality_report.json"

def canonical_title(value):
    s = unicodedata.normalize("NFKC", value or "").casefold()
    s = re.sub(r"^[●\s]+", "", s)
    s = re.sub(r"^[【\[]?(?:道の駅)?[^\]】]{1,35}[\]】]\s*", "", s)
    s = re.sub(r"\s+", "", s)
    return s

def hokuriku_article_id(record):
    """Unique official article ID, invariant across calendar display dates."""
    parsed = urlparse(record.get("url", ""))
    if (parsed.hostname not in ("www.hokuriku-michinoeki.jp", "hokuriku-michinoeki.jp")
            or parsed.path.rstrip("/") != "/contents/event"):
        return None
    article = parse_qs(parsed.query).get("article", [])
    return article[0] if len(article) == 1 and article[0] else None


def normalize_hokuriku_record(record):
    """Pin the official article URL to the event start date, not view date."""
    article = hokuriku_article_id(record)
    if not article or not record.get("startDate"):
        return record
    normalized = dict(record)
    from urllib.parse import urlencode
    normalized["url"] = ("https://www.hokuriku-michinoeki.jp/contents/event/?"
                         + urlencode({"dc": record["startDate"], "article": article}))
    return normalized


def coalesce_hokuriku_records(records):
    """Collapse only proven same-article, same-station, same-period records.

    Different official articles remain distinct even on the same day.
    """
    result, positions = [], {}
    for record in records:
        item = normalize_hokuriku_record(record)
        article = hokuriku_article_id(item)
        if not article:
            result.append(item)
            continue
        key = (article, item.get("roadName"), item.get("startDate"), item.get("endDate"))
        previous_index = positions.get(key)
        if previous_index is None:
            positions[key] = len(result)
            result.append(item)
        elif len(item.get("title", "")) < len(result[previous_index].get("title", "")):
            result[previous_index] = item
    return result


def identity(record):
    # Distinguish simultaneous events, including several entries in one PDF.
    article = hokuriku_article_id(record)
    if article:
        return ("hokuriku-article:" + article, record.get("roadName", ""), "")
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

def _sanitize_future_publication(records, today, warnings):
    """A post cannot have been published after the date we collected it.

    Do not alter the verified event period; publication metadata is optional.
    Report once even when the same record occurs in old and new collections.
    """
    result = []
    warned = {(w["url"], w["publishedAt"]) for w in warnings}
    for record in records:
        item = dict(record)
        published = item.get("publishedAt", "")
        if published:
            try:
                stamp = date.fromisoformat(published)
            except (ValueError, TypeError):
                stamp = None
            if stamp is not None and stamp > today:
                key = (item.get("url", ""), published)
                if key not in warned:
                    warnings.append({"url": key[0], "roadName": item.get("roadName", ""),
                                     "publishedAt": published,
                                     "reason": "publication_date_in_future"})
                    warned.add(key)
                item["publishedAt"] = ""
        result.append(item)
    return result


def reconcile(old, new, today):
    report = {"schemaVersion": 1, "inputPrevious": len(old), "inputCollected": len(new),
              "expiredOrInvalid": [], "corrected": [], "exactDuplicates": [],
              "possibleDuplicates": [], "notReconfirmed": [], "finalCount": 0,
              "futurePublicationDatesCleared": []}
    old_clean = coalesce_hokuriku_records(_sanitize_future_publication(
        old, today, report["futurePublicationDatesCleared"]))
    new_clean = coalesce_hokuriku_records(_sanitize_future_publication(
        new, today, report["futurePublicationDatesCleared"]))
    report["collapsedHokurikuDuplicates"] = {
        "previous": len(old) - len(old_clean),
        "collected": len(new) - len(new_clean)}
    preserved = []
    for event in old_clean:
        if not plausible(event, today):
            report["expiredOrInvalid"].append({"roadName": event.get("roadName"), "title": event.get("title")})
            continue
        if "chubu-michinoeki.org/pdf/" in event.get("url", "") and re.match(r"^\s*●\s*[～〜~]", event.get("title", "")):
            report["expiredOrInvalid"].append({"roadName": event.get("roadName"), "title": event.get("title"), "reason": "unknown_start"})
            continue
        preserved.append(event)
    # Keep same-title events on different dates separate unless their periods
    # overlap: this prevents recurring events being mistaken for corrections.
    by_id = {(identity(e), e["startDate"]): e for e in preserved}
    for event in new_clean:
        if not plausible(event, today):
            report["expiredOrInvalid"].append({"roadName": event.get("roadName"), "title": event.get("title"), "reason": "invalid_new"})
            continue
        key = (identity(event), event["startDate"])
        prev = by_id.get(key)
        if prev is None:
            overlap = [k for k, e in by_id.items()
                       if identity(e) == identity(event) and
                       e["startDate"] <= event["endDate"] and event["startDate"] <= e["endDate"]]
            if len(overlap) == 1:
                old_key = overlap[0]
                prev = by_id.pop(old_key)
        if prev is not None:
            if (prev["startDate"], prev["endDate"]) != (event["startDate"], event["endDate"]):
                report["corrected"].append({"roadName": event["roadName"], "title": event["title"],
                    "oldDates": [prev["startDate"], prev["endDate"]],
                    "newDates": [event["startDate"], event["endDate"]]})
            else:
                report["exactDuplicates"].append({"roadName": event["roadName"], "title": event["title"]})
        by_id[key] = event
    # Previously published events absent from the current collection are kept
    # but explicitly flagged for investigation (not assumed cancelled).
    collected_ids = {identity(e) for e in new_clean if plausible(e, today)}
    for event in preserved:
        if identity(event) not in collected_ids:
            report["notReconfirmed"].append({
                "roadName": event["roadName"], "title": event["title"],
                "startDate": event["startDate"], "endDate": event["endDate"],
                "url": event["url"], "reason": "not_found_in_current_collection"})
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

#!/usr/bin/env python3
"""Detect plausible event-collection blind spots without inventing events.

Consumes *existing* official-article audits; it does not scrape websites,
interpret image text, or estimate nationwide event recall. This is a
triage/health report, not a list of verified upcoming events.
"""
import json
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


def make_report(discovery, registry, coverage, quality, regional, previous=None,
                today=None):
    today = today or datetime.now(JST).date().isoformat()
    previous = previous or {}
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
            "stationCoverage": "No complete nationwide station master is connected. Only configured feeds and already published stations are counted.",
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
            "regionalHomepagesAudited": len(regional_checks),
            "targetedStationPrefectures": coverage.get("summary", {}).get("targetedStationFeedPrefectures", 0),
            "publishedStations": len(current_stations),
            "publishedStationsWithoutDirectTarget": len(published_without_target),
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
        "historicallyReachedWithNoCurrentEvents": uncovered,
        "reviewCandidates": queue[:120],
        "unreconfirmedEvents": unconfirmed,
        "warnings": warnings,
        "sources": checked_sources,
        "regionalHomepages": regional_checks,
    }


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def main():
    old = _load(OUTPUT.name) if OUTPUT.exists() else {}
    report = make_report(
        _load("station_event_discovery_audit.json"),
        _load("station_event_discovery_sources.json"),
        _load("prefecture_event_coverage.json"),
        _load("road_event_quality_report.json"),
        _load("road_event_sources_report.json"),
        previous=old)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
        OUTPUT.write_text(rendered, encoding="utf-8")
    s = report["summary"]
    print("収集漏れ監査: 設定型 {}/{}先 / 要確認候補サンプル {}件 / "
          "取得問題 {}先 / 候補0 {}先 / 検査上限 {}先 / 未再確認 {}件".format(
              s["phase2SourcesAudited"], s["phase2SourcesConfigured"],
              s["potentialReviewSamples"], s["sourcesWithFetchProblems"],
              s["sourcesWithZeroCandidates"], s["sourcesAtCheckLimit"],
              s["unreconfirmedEvents"]))
    # Warning findings must not fail the collection pipeline. Invalid
    # input/schema or code errors should still raise to make failure visible.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

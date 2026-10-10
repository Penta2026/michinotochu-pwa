#!/usr/bin/env python3
"""47-prefecture event COVERAGE report; not a claim of 47-prefecture completeness.

Three independent facts are recorded per prefecture:
- observed dated events in the published JSON;
- configured *targeted* station feeds (when explicitly known);
- reachability of a region's discovery homepage, which proves no station coverage.
Avoid calling an empty prefecture "no events" or a reachable region "supported".
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORT = DATA / "prefecture_event_coverage.json"

# Reporting groups. Each prefecture appears exactly once; these groups are
# bookkeeping, NOT proof that one regional website covers every station.
BLOCKS = {
    "北海道": ("北海道",),
    "東北": ("青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県"),
    "関東": ("茨城県", "栃木県", "群馬県", "埼玉県", "千葉県",
             "東京都", "神奈川県", "山梨県", "長野県"),
    "北陸": ("新潟県", "富山県", "石川県"),
    "中部": ("岐阜県", "静岡県", "愛知県", "三重県"),
    "近畿": ("福井県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県"),
    "中国": ("鳥取県", "島根県", "岡山県", "広島県", "山口県"),
    "四国": ("徳島県", "香川県", "愛媛県", "高知県"),
    "九州・沖縄": ("福岡県", "佐賀県", "長崎県", "熊本県",
                   "大分県", "宮崎県", "鹿児島県", "沖縄県"),
}
PREFECTURES = tuple(p for names in BLOCKS.values() for p in names)
assert len(PREFECTURES) == 47 and len(set(PREFECTURES)) == 47, "Prefecture mapping must cover all 47"

def targeted_station_sources():
    """Explicitly configured station feeds; never infer coverage from a region homepage."""
    from kyushu_okinawa_events import SOURCES as southern_sources
    from kyushu_six_prefectures import SOURCES as six_sources
    stations = defaultdict(list)
    for source in (*southern_sources, *six_sources):
        pref = source["prefecture"]
        name = source.get("name") or source.get("road")
        if pref not in PREFECTURES:
            raise ValueError(f"Unknown configured prefecture: {pref}")
        if name and name not in stations[pref]:
            stations[pref].append(name)
    # Verified official station/municipal feeds for the initial three Kanto
    # prefectures. Their presence does not imply that every station in each
    # prefecture is covered or that a current event has been extracted.
    kanto_targets = {
        "茨城県": ("かさま", "ひたちおおた"),
        "栃木県": ("ましこ",),
        "群馬県": ("あぐりーむ昭和",),
        "千葉県": ("しょうなん", "保田小学校"),
        "東京都": ("八王子滝山",),
        "神奈川県": ("湘南ちがさき",),
    }
    for pref, names in kanto_targets.items():
        for name in names:
            if name not in stations[pref]:
                stations[pref].append(name)
    # Explicit station-by-station sources for the five previously empty
    # Kinki prefectures (six feeds, not complete geographic coverage).
    from kinki_five_prefectures import SOURCES as kinki_sources
    for item in kinki_sources:
        pref, name = item["prefecture"], item["road"]
        if pref not in PREFECTURES:
            raise ValueError(f"Unknown Kinki prefecture: {pref}")
        if name not in stations[pref]:
            stations[pref].append(name)
    # Phase 2 config-only HTML sources; including an official listing URL
    # records a targeted source, not successful extraction/coverage.
    phase2_path = DATA / "station_event_discovery_sources.json"
    if phase2_path.exists():
        phase2 = json.loads(phase2_path.read_text(encoding="utf-8"))
        if phase2.get("schemaVersion") != 1:
            raise ValueError("Unknown Phase 2 discovery registry schema")
        for item in phase2.get("sources", []):
            if not item.get("enabled"):
                continue
            pref, name = item["prefecture"], item["roadName"]
            if pref not in PREFECTURES:
                raise ValueError(f"Unknown discovery prefecture: {pref}")
            if name not in stations[pref]:
                stations[pref].append(name)
    return dict(stations)

def make_report(event_data, source_report, quality_report, direct=None,
                historically_observed=None):
    direct = targeted_station_sources() if direct is None else direct
    events = event_data.get("events", [])
    by_pref = defaultdict(list)
    for item in events:
        by_pref[item.get("prefecture", "")].append(item)
    unknown_prefs = sorted(set(by_pref) - set(PREFECTURES))
    # Historical success is not the same as a currently published future event.
    # This set only grows when actual dated events reached road_events.json.
    previous_history = set(historically_observed or ())
    invalid_history = previous_history - set(PREFECTURES)
    if invalid_history:
        raise ValueError("Invalid historical prefecture(s): " +
                         ", ".join(sorted(invalid_history)))
    historical = previous_history | (set(by_pref) & set(PREFECTURES))
    by_region = {entry["region"]: entry for entry in source_report.get("sources", [])}
    unconfirmed_by_pref = Counter(
        item.get("prefecture") for item in quality_report.get("notReconfirmed", [])
        if item.get("prefecture")
    )
    # The current quality audit's notReconfirmed items omit prefecture;
    # resolve them only when exact URL + station name match a published event.
    unconfirmed_urls = {(x.get("url"), x.get("roadName"))
                        for x in quality_report.get("notReconfirmed", [])}
    prefectures = []
    groups = []
    for region, members in BLOCKS.items():
        home = by_region.get(region, {})
        region_items = []
        for pref in members:
            items = by_pref.get(pref, [])
            names = sorted(set(x.get("roadName", "") for x in items if x.get("roadName")))
            current_unconfirmed = sum(
                1 for e in items if
                (e.get("url"), e.get("roadName")) in unconfirmed_urls)
            current_unconfirmed = max(current_unconfirmed, unconfirmed_by_pref[pref])
            configured = sorted(direct.get(pref, []))
            if current_unconfirmed:
                state, action = "needs_reconfirmation", "recheck_known_event"
            elif items:
                state, action = "events_observed", "expand_station_coverage"
            elif configured:
                state, action = "targeted_feed_no_registered_events", "inspect_official_article_dates"
            else:
                state, action = "no_registered_events", "discover_prefecture_station_feeds"
            report = {
                "prefecture": pref, "reportingRegion": region,
                "eventCount": len(items), "observedStations": names,
                "historicallyObserved": pref in historical,
                "observedStationCount": len(names),
                "targetedStationFeeds": configured,
                "notReconfirmedCount": current_unconfirmed,
                "state": state, "nextAction": action,
                # Do not conflate regional homepage success with prefecture
                # news visibility or a working prefecture collector.
                "regionalHomepageReachable": home.get("reachable"),
                "regionalHomepageListingCandidates": home.get("candidateCount"),
                "regionalAuditMode": home.get("status"),
            }
            region_items.append(report)
            prefectures.append(report)
        groups.append({
            "region": region,
            "prefectureCount": len(members),
            "observedPrefectures": sum(x["eventCount"] > 0 for x in region_items),
            "zeroRegisteredPrefectures": [x["prefecture"] for x in region_items if x["eventCount"] == 0],
            "registeredEventCount": sum(x["eventCount"] for x in region_items),
            "regionalHomepageReachable": home.get("reachable"),
            "regionalHomepageListingCandidates": home.get("candidateCount"),
        })
    zero = [x["prefecture"] for x in prefectures if x["eventCount"] == 0]
    historical_names = [p for p in PREFECTURES if p in historical]
    never_names = [p for p in PREFECTURES if p not in historical]
    history_only = [p for p in PREFECTURES if p in historical and p in zero]
    urgent = [x["prefecture"] for x in prefectures if x["notReconfirmedCount"]]
    return {
        "schemaVersion": 1,
        "basisUpdatedAt": event_data.get("updatedAt", ""),
        "definitions": {
            "observed": "Only the dated events currently present in data/road_events.json.",
            "targetedFeed": "An explicitly configured station source, not proof of parsing or future-event availability.",
            "regionalHomepageReachable": "Region homepage HTTP success only; does not prove event coverage for its prefectures.",
            "zeroRegistered": "No current published event; not evidence that no events take place.",
            "historicalObserved": "At least one dated event was previously published; not proof of current upcoming events or full station coverage.",
        },
        "historical": {
            "observedPrefectures": historical_names,
            "neverObservedPrefectures": never_names,
            "previouslyObservedWithoutCurrentEvents": history_only,
        },
        "summary": {
            "prefectureCount": 47,
            "observedPrefectures": 47 - len(zero),
            "zeroRegisteredPrefectures": len(zero),
            "historicalObservedPrefectures": len(historical_names),
            "historicalNeverObservedPrefectures": len(never_names),
            "registeredEvents": len(events),
            "targetedStationFeedPrefectures": sum(bool(x["targetedStationFeeds"]) for x in prefectures),
            "notReconfirmedEvents": len(quality_report.get("notReconfirmed", [])),
            "unknownPrefectures": unknown_prefs,
        },
        "priorities": {
            "reconfirm": urgent,
            "historicalNeverObserved": never_names,
            "previouslyObservedWithoutCurrentEvents": history_only,
            "noEventsButTargetedFeed": [x["prefecture"] for x in prefectures
                                        if not x["eventCount"] and x["targetedStationFeeds"]],
            "noEventsNoTargetedFeed": [x["prefecture"] for x in prefectures
                                      if not x["eventCount"] and not x["targetedStationFeeds"]],
        },
        "regions": groups,
        "prefectures": prefectures,
    }

def _read_json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))

def main():
    # Keep the history previously published in this exact report. Do not
    # reconstruct event history from old HTTP listings or expired dates.
    previous = _read_json("prefecture_event_coverage.json") if REPORT.exists() else {}
    history = previous.get("historical", {}).get("observedPrefectures", [])
    report = make_report(
        _read_json("road_events.json"),
        _read_json("road_event_sources_report.json"),
        _read_json("road_event_quality_report.json"),
        historically_observed=history,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if not REPORT.exists() or REPORT.read_text(encoding="utf-8") != payload:
        REPORT.write_text(payload, encoding="utf-8")
    s = report["summary"]
    print(f"都道府県監査: 現在 {s['observedPrefectures']}/47県, "
          f"累計実績 {s['historicalObservedPrefectures']}/47県, "
          f"未登録 {s['zeroRegisteredPrefectures']}県, "
          f"全国イベント {s['registeredEvents']}件, "
          f"未再確認 {s['notReconfirmedEvents']}件")
    if s["unknownPrefectures"]:
        raise ValueError("Unrecognized prefecture(s): " + ", ".join(s["unknownPrefectures"]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

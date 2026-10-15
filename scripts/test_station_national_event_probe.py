"""Offline tests for nationwide station event publication gate."""
import unittest
import json
from tempfile import TemporaryDirectory
from pathlib import Path
from datetime import date
from collect_road_events import collect_national_station_stage
from station_national_event_probe import (
    safe_same_host, eligible_targets, parse_strict_event, collect,
)

TODAY = date(2026, 10, 15)
STATION = {"stationId": "RS0001", "prefecture": "広島県",
           "roadName": "サンプル道の駅", "websiteUrl": "https://road.example/",
           "articleHints": ["https://road.example/news/2026/autumn/"],
           "newStation": True, "lastChecked": ""}
URL = "https://road.example/news/2026/autumn/"
DETAIL = """<html><main><article>
<h1>秋の収穫祭を開催します</h1>
<p>開催日時：2026年11月1日（日）10:00〜15:00</p>
<p>会場：道の駅サンプル道の駅</p>
<p>地元農家が集まる収穫祭です</p>
</article></main></html>"""


class NationwideStationEventProbeTests(unittest.TestCase):
    def test_explicit_full_year_date_and_stated_onsite_venue(self):
        event, reason = parse_strict_event(DETAIL, STATION, URL, TODAY)
        self.assertEqual(reason, "")
        self.assertEqual(event["roadName"], "サンプル道の駅")
        self.assertEqual(event["startDate"], "2026-11-01")
        self.assertEqual(event["endDate"], "2026-11-01")
        self.assertEqual(event["url"], URL)

    def test_rejects_posting_date_only_or_offsite_event(self):
        for fake in (
            DETAIL.replace("開催日時：2026年11月1日", "投稿日：2026年11月1日"),
            DETAIL.replace("会場：道の駅サンプル道の駅", "会場：市民会館"),
            DETAIL.replace("2026年11月1日", "11月1日"),
            DETAIL.replace("秋の収穫祭を開催します", "イベント一覧"),
            DETAIL.replace("秋の収穫祭を開催します", "秋の収穫祭を中止します"),
        ):
            event, reason = parse_strict_event(fake, STATION, URL, TODAY)
            self.assertIsNone(event, reason)
        mixed = DETAIL.replace("</article>", "<h2>冬まつり開催</h2></article>")
        self.assertEqual(parse_strict_event(mixed, STATION, URL, TODAY)[1],
                         "no_unique_event_headline")

    def test_url_must_have_same_https_host(self):
        self.assertTrue(safe_same_host(URL, "https://road.example/"))
        for bad in ("https://evil.example/news", "http://road.example/news",
                    "https://road.example:8443/news",
                    "https://road.example/../admin"):
            self.assertFalse(safe_same_host(bad, "https://road.example/"))

    def test_only_directory_matched_and_site_mentioned_stations(self):
        queue = {"stations": [
            {"id": "RS0001", "roadName": "サンプル道の駅", "prefecture": "広島県",
             "directoryInspectionState": "checked", "candidates": [
                 {"url": "https://road.example/",
                  "kind": "station_or_partner_site_unverified"}]},
            {"id": "RS0002", "roadName": "偽の駅", "prefecture": "山形県",
             "directoryInspectionState": "not_checked", "candidates": [
                 {"url": "https://evil.example/",
                  "kind": "station_or_partner_site_unverified"}]},
        ]}
        audit = {"results": [
            {"stationId": "RS0001", "url": "https://road.example/",
             "status": "identity_mentioned_unverified", "stationNameMentioned": True,
             "eventLinkHints": [URL, "https://evil.example/other"]},
            {"stationId": "RS0002", "url": "https://evil.example/",
             "status": "identity_mentioned_unverified", "stationNameMentioned": True,
             "eventLinkHints": ["https://evil.example/fake"]},
        ]}
        targets, count = eligible_targets(queue, audit, {"sources": []}, {},
                                          TODAY, limit=60)
        self.assertEqual(count, 1)
        self.assertEqual([t["stationId"] for t in targets], ["RS0001"])
        old = {"stations": [{"stationId": "RS0001", "lastChecked": "2026-10-14"}]}
        later, count = eligible_targets(queue, audit, {"sources": []}, old, TODAY)
        self.assertEqual((later, count), ([], 0))

    def test_staging_only_future_verified_events_and_robots(self):
        calls = []
        def fetch(url):
            calls.append(url)
            return DETAIL
        staged, audit = collect([STATION], {"events": [], "stations": []},
                                TODAY, fetch, lambda url: True)
        self.assertEqual(len(staged["events"]), 1)
        self.assertEqual(audit["newlyAccepted"], 1)
        self.assertEqual(calls, [URL])
        blocked, blocked_audit = collect([STATION], {"events": [], "stations": []},
                                         TODAY, fetch, lambda url: False)
        self.assertEqual(blocked["events"], [])
        self.assertEqual(blocked_audit["todayDetails"][0]["rejectedReasons"],
                         {"robots_blocked": 1})

    def test_stage_reader_accepts_only_nonexpired_well_formed_events(self):
        good, why = parse_strict_event(DETAIL, STATION, URL, TODAY)
        self.assertEqual(why, "")
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.json"
            path.write_text(json.dumps({"schemaVersion": 1, "events": [
                good, {**good, "startDate": "2026-02-01", "endDate": "2026-02-01"},
                {**good, "status": "cancelled"}
            ]}), encoding="utf-8")
            found = collect_national_station_stage(TODAY, path)
            self.assertEqual(found, [good])
            path.write_text(json.dumps({"schemaVersion": 9, "events": [good]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                collect_national_station_stage(TODAY, path)


if __name__ == "__main__":
    unittest.main()

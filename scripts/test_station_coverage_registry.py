"""Offline, no-network tests for the all-station official-event coverage register."""
import unittest
import json
from pathlib import Path

from station_coverage_registry import (read_app_stations, website_candidates,
                                       build_inventory, render_dashboard, DATA)


class StationCoverageRegistryTests(unittest.TestCase):
    def setUp(self):
        self.roads = [
            {"id": "1", "name": "道の駅 なかまち", "prefecture": "奈良県",
             "officialUrl": "https://official.example/station"},
            {"id": "2", "name": "イベント未登録", "prefecture": "奈良県",
             "url": "https://maps.google.com/?q=station"},
            {"id": "3", "name": "道の駅 てんのう", "prefecture": "秋田県"},
        ]
        self.sources = {"sources": [
            {"id": "good", "enabled": True, "prefecture": "奈良県",
             "roadName": "なかまち",
             "listingUrl": "https://official.example/news"},
            {"id": "stopped", "enabled": False, "prefecture": "秋田県",
             "roadName": "てんのう",
             "listingUrl": "https://broken.example/404"},
        ]}
        self.audit = {"checkedOn": "2026-10-13", "sources": [
            {"id": "good", "fetchFailed": 0, "listingError": "",
             "checked": 4, "accepted": 0}]}
        self.events = {"events": [{"prefecture": "奈良県", "roadName": "なかまち",
                                   "title": "祭り", "startDate": "2026-10-30"}]}

    def build(self):
        return build_inventory(self.roads, self.sources,
                               {"sources": []}, self.events, self.audit,
                               checked_on="2026-10-13")

    def test_every_station_is_present_including_zero_event_and_disabled_source(self):
        x = self.build()
        self.assertEqual(x["summary"]["appStations"], 3)
        self.assertEqual([s["id"] for s in x["stations"]], ["1", "2", "3"])
        self.assertTrue(x["summary"]["allStationRecordsPresent"])
        self.assertEqual(x["summary"]["stationsWithCurrentVerifiedEvent"], 1)
        self.assertEqual(x["stations"][1]["coverageState"], "no_dedicated_source")
        self.assertEqual(x["stations"][2]["coverageState"], "no_dedicated_source")
        self.assertEqual(x["summary"]["confirmedNoEventStations"], 0)
        self.assertFalse(any(s["eventAbsentConfirmed"] for s in x["stations"]))

    def test_verified_article_recheck_only_does_not_mean_new_event_discovery(self):
        verified = {"sources": [{"id": "archive", "prefecture": "奈良県",
                                 "roadName": "イベント未登録"}]}
        x = build_inventory(self.roads, self.sources, verified,
                            self.events, self.audit, checked_on="2026-10-13")
        self.assertEqual(x["summary"]["individualSourcesWithListing"], 1)
        self.assertEqual(x["summary"]["individualSourcesIncludingRecheck"], 2)
        self.assertEqual(x["stations"][1]["coverageState"],
                         "dedicated_source_configured_not_checked")

    def test_legacy_regional_station_targets_are_counted_as_individual_coverage(self):
        coverage = {"prefectures": [
            {"prefecture": "秋田県", "targetedStationFeeds": ["道の駅てんのう"]},
            {"prefecture": "奈良県", "targetedStationFeeds": ["なかまち"]},
        ]}
        x = build_inventory(self.roads, self.sources, {"sources": []},
                            self.events, self.audit, coverage=coverage,
                            checked_on="2026-10-13")
        self.assertEqual(x["summary"]["individualSourcesWithListing"], 1)
        self.assertEqual(x["summary"]["stationsWithAnyDedicatedCollector"], 2)
        self.assertEqual(x["summary"]["stationsWithoutDedicatedSource"], 1)
        self.assertTrue(x["stations"][2]["dedicatedCollectorCoveredAcrossAllModes"])
        self.assertEqual(x["stations"][2]["coverageState"],
                         "other_dedicated_collector_configured")
        self.assertEqual(x["stations"][1]["nextAction"], "review_official_website_url")

    def test_directory_candidate_enriches_only_matching_station_and_stays_unverified(self):
        scan = {"stations": [
            {"id": "1", "prefecture": "奈良県", "roadName": "なかまち",
             "directoryDetailUrl": "https://www.michi-no-eki.jp/stations/views/123",
             "lastDirectoryChecked": "2026-10-13",
             "officialWebsiteCandidateUrlsUnverified": [
                 "https://directory-hint.example/road"]},
            {"id": "2", "prefecture": "北海道", "roadName": "イベント未登録",
             "directoryDetailUrl": "https://www.michi-no-eki.jp/stations/views/456",
             "lastDirectoryChecked": "2026-10-13",
             "officialWebsiteCandidateUrlsUnverified": [
                 "https://wrong-station.example/"]},
        ]}
        x = build_inventory(self.roads, self.sources, {"sources": []},
                            self.events, self.audit, directory=scan,
                            checked_on="2026-10-13")
        self.assertEqual(x["summary"]["nationalDirectoryStationPagesChecked"], 1)
        self.assertEqual(x["summary"]["nationalDirectoryLinkCandidateStations"], 1)
        self.assertIn("https://directory-hint.example/road",
                      x["stations"][0]["officialWebsiteCandidateUrlsUnverified"])
        self.assertEqual(x["stations"][1]["officialWebsiteCandidateUrlsUnverified"], [])
        self.assertFalse(x["stations"][0]["officialSiteOwnershipVerified"])
        self.assertEqual(x["summary"]["stationsWithAnyDedicatedCollector"], 1)
        self.assertEqual(x["summary"]["confirmedNoEventStations"], 0)

    def test_directory_candidate_creates_verification_action_not_event(self):
        scan = {"stations": [{
            "id": "2", "prefecture": "奈良県", "roadName": "イベント未登録",
            "lastDirectoryChecked": "2026-10-13",
            "directoryDetailUrl": "https://www.michi-no-eki.jp/stations/views/456",
            "officialWebsiteCandidateUrlsUnverified": ["https://maybe-official.example/"],
        }]}
        result=build_inventory(self.roads,self.sources,{"sources":[]},
                               self.events,self.audit,directory=scan,
                               checked_on="2026-10-13")
        station=result["stations"][1]
        self.assertEqual(station["coverageState"],"no_dedicated_source")
        self.assertEqual(station["nextAction"],"verify_station_site_candidate")
        self.assertEqual(station["currentVerifiedEvents"],0)
        self.assertFalse(station["eventAbsentConfirmed"])

    def test_website_hints_cannot_be_treated_as_verified_official_sources(self):
        x = self.build()["stations"]
        self.assertEqual(x[0]["officialWebsiteCandidateUrlsUnverified"],
                         ["https://official.example/station"])
        self.assertEqual(x[1]["officialWebsiteCandidateUrlsUnverified"], [])
        self.assertEqual(x[0]["dedicatedOfficialListingUrls"],
                         ["https://official.example/news"])
        self.assertNotIn("https://official.example/station",
                         x[0]["dedicatedOfficialListingUrls"])

    def test_master_parser_enforces_expected_length_and_unique_station_ids(self):
        raw = ('window.APP_DATA='+json.dumps({
            "meta": {"roadStations": 2},
            "roads": self.roads[:2]}, ensure_ascii=False) + ';')
        self.assertEqual(len(read_app_stations(raw)), 2)
        with self.assertRaises(ValueError):
            read_app_stations(raw.replace('"roadStations": 2', '"roadStations": 3'))
        with self.assertRaises(ValueError):
            read_app_stations('window.APP_DATA='+json.dumps({
                "roads": [self.roads[0], self.roads[0]]},ensure_ascii=False))

    def test_dashboard_states_inventory_is_not_full_coverage_or_no_events(self):
        report = render_dashboard(self.build())
        self.assertIn("すべての駅を管理対象", report)
        self.assertIn("すべての駅の公式サイトを実際に見に行った", report)
        self.assertIn("イベントが存在しない", report)

    def test_real_repository_master_has_all_1234_app_station_records(self):
        roads = read_app_stations((DATA/"app_data.js").read_text(encoding="utf-8"))
        self.assertEqual(len(roads), 1234)
        self.assertEqual(len({r["id"] for r in roads}), len(roads))


if __name__ == "__main__":
    unittest.main()

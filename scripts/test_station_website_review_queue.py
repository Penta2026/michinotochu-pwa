"""Offline regression tests for Phase 11 website review queue."""
import unittest
from station_website_review_queue import build_queue, classify

class WebsiteReviewQueueTests(unittest.TestCase):
    def test_regional_portal_is_not_station_ownership(self):
        self.assertEqual(classify("http://www.hokkaido-michinoeki.jp/michinoeki/172/"), "regional_directory")

    def test_no_ownership_or_event_inferred(self):
        result = build_queue({"lastChecked": "2026-10-13", "stations": [
            {"id": "RS0001", "prefecture": "北海道", "roadName": "三笠",
             "officialWebsiteCandidateUrlsUnverified": [
                 "http://www.hokkaido-michinoeki.jp/michinoeki/172/",
                 "https://sample-station.example/events"]}]})
        station = result["stations"][0]
        self.assertEqual(station["candidates"][0]["url"], "https://sample-station.example/events")
        self.assertFalse(station["candidates"][0]["ownershipVerified"])
        self.assertFalse(station["candidates"][0]["eventListingVerified"])
        self.assertEqual(station["eventCoverageState"], "not_assessed")
        self.assertEqual(result["stationsReviewed"], 0)

    def test_empty_site_is_not_no_events(self):
        station = build_queue({"stations": [{"id": "RS0010", "prefecture": "北海道", "roadName": "摩周温泉", "officialWebsiteCandidateUrlsUnverified": []}]})["stations"][0]
        self.assertEqual(station["siteVerificationState"], "no_candidate_found")
        self.assertEqual(station["eventCoverageState"], "not_assessed")

    def test_rejects_duplicate_station_id(self):
        row = {"id": "RS0001", "prefecture": "北海道", "roadName": "三笠"}
        with self.assertRaises(ValueError):
            build_queue({"stations": [row, row]})

    def test_full_master_includes_not_yet_checked_stations(self):
        master = {"summary": {"appStations": 2}, "stations": [
            {"id": "RS0001", "prefecture": "北海道", "roadName": "三笠"},
            {"id": "RS0002", "prefecture": "北海道", "roadName": "南ふらの"}]}
        directory = {"stations": [{"id": "RS0001", "prefecture": "北海道",
                       "roadName": "三笠", "officialWebsiteCandidateUrlsUnverified":
                       ["https://sample.example/"]}]}
        result = build_queue(directory, master)
        self.assertEqual(result["masterStationCount"], 2)
        self.assertEqual(result["directoryStationsInspected"], 1)
        self.assertEqual(result["stations"][1]["directoryInspectionState"], "not_checked")
        self.assertEqual(result["stations"][1]["homepageExistence"], "unknown")
        self.assertEqual(result["stations"][1]["eventCoverageState"], "not_assessed")

    def test_old_http_station_links_get_unverified_https_trial(self):
        r = build_queue({"stations": [{"id": "RS0020", "prefecture": "広島県",
            "roadName": "試験道の駅", "officialWebsiteCandidateUrlsUnverified":
            ["http://station.example/news/"]}]})
        row = r["stations"][0]
        secure = next(c for c in row["candidates"] if c["url"].startswith("https:"))
        self.assertEqual(secure["directoryOriginalUrl"], "http://station.example/news/")
        self.assertTrue(secure["httpsUpgradeUnverified"])
        self.assertFalse(secure["ownershipVerified"])
        self.assertFalse(secure["eventListingVerified"])

    def test_rejects_suspicious_urls(self):
        self.assertEqual(classify("file:///etc/passwd"), "invalid")
        self.assertEqual(classify("http://localhost/admin"), "invalid")
        self.assertEqual(classify("https://user:pass@site.example/"), "invalid")

if __name__ == "__main__":
    unittest.main()

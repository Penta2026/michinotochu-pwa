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

    def test_rejects_suspicious_urls(self):
        self.assertEqual(classify("file:///etc/passwd"), "invalid")
        self.assertEqual(classify("http://localhost/admin"), "invalid")
        self.assertEqual(classify("https://user:pass@site.example/"), "invalid")

if __name__ == "__main__":
    unittest.main()

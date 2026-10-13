import unittest
from datetime import date
from national_published_event_quality import audit


class PublishedQualityTests(unittest.TestCase):
    def setUp(self):
        self.station = {"prefecture": "富山県", "name": "テスト駅"}
        self.event = {"prefecture": "富山県", "roadName": "テスト駅",
                      "title": "秋祭り", "startDate": "2026-10-14", "endDate": "2026-10-15",
                      "url": "https://example.org/event"}

    def test_valid_event_passes(self):
        result = audit([self.event], [self.station], date(2026, 10, 13))
        self.assertEqual(result["criticalCount"], 0)
        self.assertEqual(result["manualReviewCount"], 0)

    def test_expired_unsafe_and_duplicate_fail(self):
        row = dict(self.event, endDate="2026-10-12", url="http://example.org/event")
        result = audit([row, row], [self.station], date(2026, 10, 13))
        reasons = {x["reason"] for x in result["critical"]}
        self.assertIn("expired_event", reasons)
        self.assertIn("unsafe_or_missing_official_link", reasons)
        self.assertIn("exact_publication_duplicate", reasons)

    def test_long_duration_and_unknown_station_remain_review(self):
        row = dict(self.event, roadName="不明駅", endDate="2027-03-14")
        result = audit([row], [self.station], date(2026, 10, 13))
        self.assertEqual(result["criticalCount"], 0)
        self.assertEqual(result["manualReviewCount"], 2)


if __name__ == "__main__":
    unittest.main()

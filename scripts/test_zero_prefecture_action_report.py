import unittest
from zero_prefecture_action_report import build


class ZeroPrefectureReportTests(unittest.TestCase):
    def test_every_zero_prefecture_has_a_concrete_review_path(self):
        coverage = {"basisUpdatedAt": "2026-10-13", "prefectures": [
            {"prefecture": "甲県", "eventCount": 0, "reportingRegion": "中部"},
            {"prefecture": "乙県", "eventCount": 1, "reportingRegion": "中部"}]}
        discovery = {"sources": [{"prefecture": "甲県", "id": "official",
            "candidates": 5, "checked": 3, "accepted": 0,
            "uninspectedCandidates": 2, "reasons": {"undated": 2}}]}
        leads = {"sources": [{"prefecture": "甲県", "url": "https://example.org/events/"}]}
        result = build(coverage, discovery, leads)
        self.assertEqual(result["prefecturesWithoutCurrentEvents"], 1)
        self.assertEqual(result["prefecturesWithOfficialReviewLeads"], 1)
        self.assertEqual(result["prefectures"][0]["articlesChecked"], 3)
        self.assertEqual(result["prefectures"][0]["rejectionReasons"]["undated"], 2)
        self.assertEqual(result["prefectures"][0]["currentEvents"], 0)
        self.assertEqual(result["uncoveredPrefectures"], [])

    def test_missing_lead_does_not_claim_verified_coverage(self):
        report = build({"prefectures": [{"prefecture": "甲県", "eventCount": 0}]},
                       {"sources": []}, {"sources": []})
        self.assertEqual(report["uncoveredPrefectures"], ["甲県"])
        self.assertEqual(report["prefecturesWithOfficialReviewLeads"], 0)


if __name__ == "__main__":
    unittest.main()

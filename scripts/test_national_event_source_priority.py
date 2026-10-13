import unittest
from national_event_source_priority import make_report

class NationwidePriorityTests(unittest.TestCase):
    def test_region_gap_does_not_claim_no_events_or_verified_coverage(self):
        coverage = {"summary": {"observedPrefectures": 36, "zeroRegisteredPrefectures": 11},
                    "regions": [{"region": "北陸", "prefectureCount": 3, "zeroRegisteredPrefectures": ["富山県"],
                                 "registeredEventCount": 4}]}
        audit = {"sources": [{"region": "北陸", "reachable": True, "status": "discovery",
                              "url": "https://example.org", "candidateCount": 3}]}
        result = make_report(coverage, audit)
        self.assertEqual(result["regions"][0]["nextAction"], "verify_event_listing_and_build_safe_adapter")
        self.assertEqual(result["regions"][0]["prefecturesWithoutCurrentPublishedEvents"], ["富山県"])
        self.assertEqual(result["highTrafficStationPriority"]["state"], "awaiting_objective_visitation_evidence")

    def test_prefecture_evidence_count(self):
        coverage = {"summary": {"observedPrefectures": 0, "zeroRegisteredPrefectures": 1},
                    "regions": [{"region": "北陸", "prefectureCount": 1,
                                 "zeroRegisteredPrefectures": ["富山県"], "registeredEventCount": 0}],
                    "prefectures": [{"prefecture": "富山県", "reportingRegion": "北陸",
                                     "eventCount": 0, "targetedStationFeeds": [],
                                     "regionalHomepageReachable": True}]}
        audit = {"sources": [{"region": "北陸", "reachable": True, "status": "discovery"}]}
        result = make_report(coverage, audit)
        self.assertEqual(result["prefectureEvidenceCount"], 1)
        self.assertEqual(result["regions"][0]["prefectureEvidence"][0]["evidenceLevel"],
                         "regional_homepage_only_or_unknown")

    def test_unreachable_source_gets_first_priority(self):
        coverage = {"summary": {"observedPrefectures": 1, "zeroRegisteredPrefectures": 1},
                    "regions": [{"region": "東北", "prefectureCount": 1,
                                 "zeroRegisteredPrefectures": [], "registeredEventCount": 3},
                                {"region": "北海道", "prefectureCount": 1,
                                 "zeroRegisteredPrefectures": ["北海道"], "registeredEventCount": 0}]}
        audit = {"sources": [{"region": "東北", "reachable": True, "status": "adapter"},
                             {"region": "北海道", "reachable": False, "status": "discovery"}]}
        self.assertEqual(make_report(coverage, audit)["regions"][0]["region"], "北海道")

if __name__ == "__main__":
    unittest.main()

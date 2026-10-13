"""Offline checks for nationwide event data acceptance."""
import unittest
from national_collection_acceptance import check, REGIONS, AUDITS


class CollectionAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.prefectures = [{"prefecture": "県"+str(i), "eventCount": 0} for i in range(47)]
        self.coverage = {
            "prefectures": self.prefectures,
            "summary": {"registeredEvents": 0, "zeroRegisteredPrefectures": 47},
            "regions": [{"region": region} for region in REGIONS],
        }
        self.sources = {"sources": [{"region": region, "reachable": True} for region in REGIONS]}
        self.priority = {"regions": [{"region": region} for region in REGIONS]}

    def test_valid_structure_does_not_claim_nine_successful_collectors(self):
        result = check(self.coverage, self.sources, self.priority, {},
                       "2026-10-13")
        self.assertTrue(result["structurallyValid"])
        self.assertEqual(len(result["warnings"]), 9)
        self.assertIsNone(result["regions"][0]["adapterAuditIsFresh"])

    def test_mismatched_events_fail(self):
        self.coverage["summary"]["registeredEvents"] = 2
        result = check(self.coverage, self.sources, self.priority, {},
                       "2026-10-13")
        self.assertFalse(result["structurallyValid"])
        self.assertIn("published_event_count_mismatch", result["blockingIssues"])

    def test_old_snapshot_is_warning_not_verified_current_run(self):
        audits = {AUDITS["四国"]: {"schemaVersion": 1, "checkedOn": "2026-10-12"}}
        result = check(self.coverage, self.sources, self.priority, audits,
                       "2026-10-13")
        self.assertTrue(result["structurallyValid"])
        self.assertIn("stale_adapter_audit:四国", result["warnings"])
        self.assertFalse(next(r for r in result["regions"] if r["region"] == "四国")["adapterAuditIsFresh"])

    def test_missing_region_and_stale_audit_are_visible(self):
        self.sources["sources"] = self.sources["sources"][:-1]
        audits = {AUDITS["北海道"]: {"schemaVersion": 1, "checkedOn": "2026-10-12"}}
        result = check(self.coverage, self.sources, self.priority, audits,
                       "2026-10-13")
        self.assertFalse(result["structurallyValid"])
        self.assertIn("regional_source_audit_missing_regions", result["blockingIssues"])
        self.assertFalse(result["regions"][0]["adapterAuditIsFresh"])


if __name__ == "__main__":
    unittest.main()

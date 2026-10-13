import unittest
from station_website_priority import build


class StationWebsitePriorityTests(unittest.TestCase):
    def test_priority_never_promotes_unverified_links_to_events(self):
        rows = [{"id": "RS%04d" % (i+1), "prefecture": "富山県" if i == 0 else "北海道",
                 "roadName": "テスト駅", "directoryInspectionState": "checked" if i < 2 else "not_checked",
                 "candidates": ([{"url": "https://example.org", "kind": "station_or_partner_site_unverified",
                                  "reviewStatus": "awaiting_review"}] if i == 0 else [])}
                for i in range(1234)]
        result = build({"stations": rows}, ["富山県"])
        self.assertEqual(result["directoryRemaining"], 1232)
        self.assertEqual(result["zeroCurrentEventPrefectureCandidates"], 1)
        self.assertFalse(result["reviewPriority"][0]["verified"])

    def test_unique_master_ids_required(self):
        rows = [{"id": "duplicate", "directoryInspectionState": "not_checked"} for _ in range(1234)]
        with self.assertRaises(ValueError):
            build({"stations": rows}, [])


if __name__ == "__main__":
    unittest.main()

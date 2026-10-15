import unittest
from station_website_batch_review import run, eligible


class BatchReviewTests(unittest.TestCase):
    def test_bounded_batch_and_persisted_cursor(self):
        rows = [{"id": "RS%04d" % i, "prefecture": "北海道",
                 "roadName": "テスト駅", "directoryInspectionState": "checked",
                 "candidates": [{"url": "https://station.example/%s" % i,
                    "kind": "station_or_partner_site_unverified",
                    "reviewStatus": "awaiting_review"}]} for i in range(1, 41)]
        queue = {"stations": rows}
        class Response:
            status_code = 200
            content = "<html><body>テスト駅 <a href='/events'>イベント</a></body></html>".encode()
        first = run(queue, {}, lambda url: Response(), lambda url: True)
        self.assertEqual(first["newlyChecked"], 36)
        self.assertEqual(first["nextBatchEligible"], 4)
        self.assertFalse(first["results"][0]["ownershipVerified"])
        self.assertEqual(first["results"][0]["eventLinkHints"], ["https://station.example/events"])
        second = run(queue, first, lambda url: Response(), lambda url: True)
        self.assertEqual(second["newlyChecked"], 4)
        self.assertEqual(len(second["results"]), 40)

    def test_respects_robots_and_never_fetches_disallowed_url(self):
        queue = {"stations": [{"id": "RS0001", "prefecture": "北海道",
                "roadName": "テスト駅", "directoryInspectionState": "checked",
                "candidates": [{"url": "https://station.example/",
                    "kind": "station_or_partner_site_unverified",
                    "reviewStatus": "awaiting_review"}]}]}
        result = run(queue, {}, lambda url: self.fail("Must not fetch"),
                     lambda url: False)
        self.assertEqual(result["results"][0]["status"], "robots_blocked")

    def test_priority_order_preserves_queue_membership_and_budget(self):
        rows = []
        for i in range(1, 5):
            rows.append({"id": "RS%04d" % i, "prefecture": "広島県",
                "roadName": "テスト駅", "directoryInspectionState": "checked",
                "candidates": [{"url": "https://station.example/%d" % i,
                    "kind": "station_or_partner_site_unverified",
                    "reviewStatus": "awaiting_review"}]})
        queue = {"stations": rows}
        class Response:
            status_code = 200
            content = b"<html><body>test</body></html>"
        ordered = [{"stationId": "RS0004", "url": "https://station.example/4"},
                   {"stationId": "RS0002", "url": "https://station.example/2"},
                   {"stationId": "RS9999", "url": "https://unsafe.example"}]
        called = []
        def fetch(url):
            called.append(url)
            return Response()
        result = run(queue, {}, fetch, lambda url: True, limit=2, priority=ordered)
        self.assertEqual(called, ["https://station.example/4", "https://station.example/2"])
        self.assertEqual(result["newlyChecked"], 2)
        self.assertEqual(result["nextBatchEligible"], 2)
        self.assertFalse(any(r["url"] == "https://unsafe.example"
                             for r in result["results"]))

    def test_budget_cap(self):
        with self.assertRaises(ValueError):
            run({"stations": []}, {}, lambda url: None, lambda url: True, limit=37)


if __name__ == "__main__":
    unittest.main()

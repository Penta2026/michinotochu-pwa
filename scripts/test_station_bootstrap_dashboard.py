import unittest
from datetime import date
from station_bootstrap_dashboard import render


class NationalBootstrapDashboardTests(unittest.TestCase):
    def test_counts_inspected_versus_officially_matched_without_inventing_events(self):
        stations = [{"id": "RS0001", "directoryCheckStatus": "directory_identity_checked"},
                    {"id": "RS0002", "directoryCheckStatus": "http_404"}]
        text = render(
            {"stations": stations, "lastDirectoryError": "Directory listing unavailable"},
            {"results": [{"stationId": "RS0001", "url": "https://example.org",
                          "status": "identity_mentioned_unverified"}]},
            {"stations": []},
            {"events": [{"title": "Sample"}]}, today=date(2026, 10, 15))
        self.assertIn("公式名簿で調査した駅 | 2駅", text)
        self.assertIn("名簿未調査 | 1232駅", text)
        self.assertIn("ホームページ候補にアクセスした駅 | 1駅", text)
        self.assertIn("現在公開中の全国イベント | 1件", text)
        self.assertIn("保存済みカーソルを維持", text)

    def test_duplicate_identity_rejected(self):
        with self.assertRaises(ValueError):
            render({"stations": [{"id": "RS0001"}, {"id": "RS0001"}]},
                   {}, {}, {}, today=date(2026, 10, 15))


if __name__ == "__main__":
    unittest.main()

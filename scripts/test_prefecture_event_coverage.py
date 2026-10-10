"""Offline regression tests for 47-prefecture event-coverage reporting."""
import unittest
from prefecture_event_coverage import BLOCKS, PREFECTURES, make_report, targeted_station_sources

class PrefectureCoverageTests(unittest.TestCase):
    def test_47_unique_prefectures(self):
        self.assertEqual(len(PREFECTURES), 47)
        self.assertEqual(len(set(PREFECTURES)), 47)
        self.assertEqual(len(BLOCKS), 9)
        self.assertIn("沖縄県", PREFECTURES)
        self.assertIn("東京都", PREFECTURES)

    def _example(self):
        events = {
            "updatedAt": "2026-10-10",
            "events": [
                {"prefecture": "北海道", "roadName": "たきかわ",
                 "title": "大収穫祭", "url": "https://official.example/hokkaido1",
                 "startDate": "2026-10-17", "endDate": "2026-10-18"},
                {"prefecture": "大分県", "roadName": "耶馬トピア",
                 "title": "竹の千灯籠夜", "url": "https://official.example/oita1",
                 "startDate": "2026-10-10", "endDate": "2026-10-12"},
            ],
        }
        homes = {"sources": [
            {"region": "北海道", "reachable": True, "candidateCount": 12, "status": "discovery"},
            {"region": "九州・沖縄", "reachable": True, "candidateCount": 0, "status": "discovery"},
        ]}
        quality = {"notReconfirmed": [{
            "roadName": "たきかわ", "url": "https://official.example/hokkaido1",
            "startDate": "2026-10-17", "endDate": "2026-10-18"}]}
        direct = {"熊本県": ["すいかの里植木"], "大分県": ["耶馬トピア"]}
        return make_report(events, homes, quality, direct=direct)

    def test_counts_and_all_prefectures(self):
        report = self._example()
        counts = report["summary"]
        self.assertEqual(counts["prefectureCount"], 47)
        self.assertEqual(counts["registeredEvents"], 2)
        self.assertEqual(counts["observedPrefectures"], 2)
        self.assertEqual(counts["zeroRegisteredPrefectures"], 45)
        self.assertEqual(sum(x["registeredEventCount"] for x in report["regions"]), 2)
        self.assertEqual(len(report["prefectures"]), 47)

    def test_distinguish_regional_homepage_from_targeted_feed(self):
        report = self._example()
        by_pref = {x["prefecture"]: x for x in report["prefectures"]}
        self.assertEqual(by_pref["熊本県"]["state"], "targeted_feed_no_registered_events")
        self.assertEqual(by_pref["熊本県"]["targetedStationFeeds"], ["すいかの里植木"])
        self.assertTrue(by_pref["熊本県"]["regionalHomepageReachable"])
        self.assertEqual(by_pref["熊本県"]["regionalHomepageListingCandidates"], 0)
        self.assertEqual(by_pref["福岡県"]["state"], "no_registered_events")
        self.assertEqual(by_pref["東京都"]["nextAction"], "discover_prefecture_station_feeds")

    def test_unconfirmed_is_matched_by_existing_official_url(self):
        report = self._example()
        hokkaido = next(x for x in report["prefectures"] if x["prefecture"] == "北海道")
        self.assertEqual(hokkaido["state"], "needs_reconfirmation")
        self.assertEqual(hokkaido["notReconfirmedCount"], 1)
        self.assertEqual(report["priorities"]["reconfirm"], ["北海道"])
        self.assertEqual(report["summary"]["notReconfirmedEvents"], 1)

    def test_factual_evidence_not_exaggerated(self):
        report = self._example()
        self.assertIn("not evidence that no events", report["definitions"]["zeroRegistered"])
        self.assertIn("does not prove event coverage", report["definitions"]["regionalHomepageReachable"])
        self.assertEqual(report["basisUpdatedAt"], "2026-10-10")

    def test_configured_station_feeds_include_three_kanto_prefectures(self):
        sources = targeted_station_sources()
        self.assertEqual(set(sources), {
            "茨城県", "栃木県", "群馬県",
            "福岡県", "佐賀県", "長崎県", "熊本県",
            "大分県", "宮崎県", "鹿児島県", "沖縄県"})
        self.assertEqual(sources["茨城県"], ["かさま", "ひたちおおた"])
        self.assertEqual(sources["栃木県"], ["ましこ"])
        self.assertEqual(sources["群馬県"], ["あぐりーむ昭和"])

    def test_unknown_prefecture_is_detected(self):
        report = make_report(
            {"updatedAt": "2026-10-10", "events": [
                {"prefecture": "架空県", "roadName": "テスト駅", "url": "https://example.org"}]},
            {"sources": []},
            {"notReconfirmed": []}, direct={})
        self.assertEqual(report["summary"]["unknownPrefectures"], ["架空県"])

if __name__ == "__main__":
    unittest.main()

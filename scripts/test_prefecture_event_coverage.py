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
            "千葉県", "東京都", "神奈川県",
            "岩手県", "山形県", "福島県", "静岡県",
            "福井県", "京都府", "大阪府", "奈良県", "和歌山県",
            "山口県", "愛媛県",
            "福岡県", "佐賀県", "長崎県", "熊本県",
            "大分県", "宮崎県", "鹿児島県", "沖縄県"})
        self.assertEqual(sources["茨城県"], ["かさま", "ひたちおおた"])
        self.assertEqual(sources["栃木県"], ["ましこ"])
        self.assertEqual(sources["群馬県"], ["あぐりーむ昭和"])
        self.assertEqual(sources["千葉県"], ["しょうなん", "保田小学校"])
        self.assertEqual(sources["東京都"], ["八王子滝山"])
        self.assertEqual(sources["神奈川県"], ["湘南ちがさき"])
        self.assertEqual(sources["福井県"], ["若狭美浜はまびより", "南えちぜん山海里"])
        self.assertEqual(sources["京都府"], ["和", "京丹波 味夢の里"])
        self.assertEqual(sources["大阪府"], ["いずみ山愛の里", "奥河内くろまろの郷"])
        self.assertEqual(sources["奈良県"], ["クロスウェイなかまち"])
        # New verified official stations can be appended without invalidating
        # previously configured feeds or accidentally duplicating a station.
        wakayama = sources["和歌山県"]
        self.assertEqual(wakayama[:3], ["ねごろ歴史の丘", "海南サクアス", "四季の郷公園"])
        self.assertIn("青洲の里", wakayama)
        self.assertEqual(wakayama.count("青洲の里"), 1)
        self.assertEqual(len(wakayama), len(set(wakayama)))
        self.assertEqual(sources["岩手県"], ["遠野風の丘"])
        self.assertEqual(sources["山形県"], ["たかはた"])
        self.assertEqual(sources["福島県"], ["ふくしま"])
        self.assertEqual(sources["静岡県"], ["伊豆ゲートウェイ函南"])
        self.assertEqual(sources["山口県"], ["あいお", "阿武町"])
        self.assertIn("あそ望の郷くぎの", sources["熊本県"])
        self.assertIn("都城NiQLL", sources["宮崎県"])
        self.assertIn("ひまわり", sources["長崎県"])
        self.assertIn("たるみずはまびら", sources["鹿児島県"])
        self.assertEqual(sources["愛媛県"].count("八幡浜みなっと"), 1)
        self.assertEqual(sources["愛媛県"], ["八幡浜みなっと"])
        self.assertIn("奥河内くろまろの郷", sources["大阪府"])
        self.assertIn("南えちぜん山海里", sources["福井県"])

    def test_historical_achievement_persists_after_event_expires(self):
        report=make_report(
            {"updatedAt":"2026-10-11","events":[
                {"prefecture":"大分県","roadName":"耶馬トピア",
                 "title":"竹の千灯籠夜","url":"https://example.org/event",
                 "startDate":"2026-10-11","endDate":"2026-10-12"}]},
            {"sources":[]}, {"notReconfirmed":[]}, direct={},
            historically_observed=["滋賀県","北海道"])
        summary=report["summary"]
        self.assertEqual(summary["observedPrefectures"],1)
        self.assertEqual(summary["historicalObservedPrefectures"],3)
        self.assertEqual(summary["historicalNeverObservedPrefectures"],44)
        self.assertEqual(report["historical"]["previouslyObservedWithoutCurrentEvents"],
                         ["北海道","滋賀県"])
        self.assertTrue(next(x for x in report["prefectures"]
                             if x["prefecture"]=="滋賀県")["historicallyObserved"])
        self.assertEqual(summary["zeroRegisteredPrefectures"],46)

    def test_historical_registry_never_accepts_unknown_prefectures(self):
        with self.assertRaisesRegex(ValueError,"Invalid historical prefecture"):
            make_report({"events":[]},{"sources":[]},{"notReconfirmed":[]},
                        direct={},historically_observed=["架空県"])
        self.assertEqual(make_report(
            {"events":[]},{"sources":[]},{"notReconfirmed":[]},direct={},
            historically_observed=["北海道","北海道"]
        )["summary"]["historicalObservedPrefectures"],1)

    def test_unknown_prefecture_is_detected(self):
        report = make_report(
            {"updatedAt": "2026-10-10", "events": [
                {"prefecture": "架空県", "roadName": "テスト駅", "url": "https://example.org"}]},
            {"sources": []},
            {"notReconfirmed": []}, direct={})
        self.assertEqual(report["summary"]["unknownPrefectures"], ["架空県"])

if __name__ == "__main__":
    unittest.main()

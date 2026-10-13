"""Phase 16 Kanto station master and onsite-venue checks."""
import unittest
from datetime import date
from kanto_events import station_index, resolve_station, onsite_venue, event_period

class KantoMasterMatchingTests(unittest.TestCase):
    def setUp(self):
        self.index = station_index([
            {"id": "RS1", "name": "こすげ", "prefecture": "山梨県"},
            {"id": "RS2", "name": "庄和", "prefecture": "埼玉県"},
            {"id": "RS3", "name": "架空同名", "prefecture": "長野県"},
            {"id": "RS4", "name": "架空同名", "prefecture": "群馬県"}])

    def test_unique_station_title(self):
        self.assertEqual(resolve_station("【こすげ】収穫祭", self.index)["id"], "RS1")

    def test_ambiguous_station_rejected(self):
        self.assertIsNone(resolve_station("【架空同名】秋まつり", self.index))

    def test_labelled_onsite_venue_required(self):
        self.assertTrue(onsite_venue("開催場所：道の駅こすげ 広場にて実施", "こすげ"))
        self.assertFalse(onsite_venue("開催場所：市役所前広場", "こすげ"))
        self.assertFalse(onsite_venue("道の駅こすげの近隣で開催", "こすげ"))
        self.assertFalse(onsite_venue("会場：市役所。道の駅こすげでも宣伝", "こすげ"))
        self.assertTrue(onsite_venue("会場：道の駅こすげ 交流広場", "こすげ"))
        self.assertTrue(onsite_venue("開催場所 : 道の駅 こすげ 交流広場", "こすげ"))
        self.assertTrue(onsite_venue("日時：10月24日。会場：道の駅こすげ", "こすげ"))
        self.assertFalse(onsite_venue("会場 : 市役所前広場。主催：道の駅こすげ", "こすげ"))

    def test_venue_does_not_confuse_other_station_or_organizer(self):
        self.assertFalse(onsite_venue("主催：道の駅こすげ。会場：市民ホール", "こすげ"))
        self.assertFalse(onsite_venue("会場：道の駅こすげ以外の場所", "こすげ"))
        self.assertTrue(onsite_venue("開催日時：10月24日\n会場：道の駅こすげ 広場", "こすげ"))

    def test_iso_and_slash_event_dates_are_grounded(self):
        self.assertEqual(event_period("2026/10/24 秋のマルシェ", None),
                         ("2026-10-24", "2026-10-24"))
        self.assertEqual(event_period("10/24 秋のマルシェ", date(2026, 10, 1)),
                         ("2026-10-24", "2026-10-24"))
        self.assertIsNone(event_period("10/24 秋のマルシェ", None))
        self.assertIsNone(event_period("2026/02/31 秋のマルシェ", None))

    def test_explicit_year_does_not_require_publication_stamp(self):
        self.assertEqual(event_period("2026年10月24日 秋のマルシェ", None),
                         ("2026-10-24", "2026-10-24"))
        self.assertIsNone(event_period("10月24日 秋のマルシェ", None))

if __name__ == "__main__":
    unittest.main()

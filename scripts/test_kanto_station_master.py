"""Phase 16 Kanto station master and onsite-venue checks."""
import unittest
from kanto_events import station_index, resolve_station, onsite_venue

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

if __name__ == "__main__":
    unittest.main()

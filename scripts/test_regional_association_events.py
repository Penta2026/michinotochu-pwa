"""Offline regression checks for association event date parsing."""
import unittest
from datetime import date
from regional_association_events import _period
from region_official_events import _murata_period
from generic_region_events import period as generic_period
from collect_road_events import chugoku_period
from hokkaido_events import parse_dates

class DateParsingTests(unittest.TestCase):
    def test_explicit_two_day(self):
        self.assertEqual(_period("開催期間 2026年10月17日～10月18日"),
                         ("2026-10-17", "2026-10-18"))

    def test_month_boundary(self):
        self.assertEqual(_period("10/30～11月3日 秋の洋らん展", date(2026, 10, 1)),
                         ("2026-10-30", "2026-11-03"))

    def test_murata_apple_to_november(self):
        self.assertEqual(_murata_period("2026年10月30日（金）～11月3日（火） 午前10時～"),
                         ("2026-10-30", "2026-11-03"))

    def test_murata_beef_festival(self):
        self.assertEqual(_murata_period("2026年10月16日（金）～18日（日） 午前9時～"),
                         ("2026-10-16", "2026-10-18"))

    def test_generic_region_dates(self):
        self.assertEqual(generic_period("2026年10月30日（金）～11月3日（火）"),
                         ("2026-10-30", "2026-11-03"))

    def test_generic_reject_invalid(self):
        self.assertIsNone(generic_period("2026年2月31日"))

    def test_chugoku_explicit_period(self):
        self.assertEqual(chugoku_period("第6回 秋フェスタ 10月24日(土)10時から", date(2026, 10, 1)),
                         ("2026-10-24", "2026-10-24"))

    def test_chugoku_multiple_dates(self):
        self.assertEqual(chugoku_period("秋の祭 10月17日(土)～10月18日(日)", date(2026, 10, 1)),
                         ("2026-10-17", "2026-10-18"))

    def test_chugoku_old_year(self):
        self.assertIsNone(chugoku_period("秋祭り 2025年10月24日", date(2025, 10, 1)))

    def test_hokkaido_takikawa_two_days(self):
        self.assertEqual(parse_dates("2026年10月17日、18日", date(2026, 10, 10)),
                         ("2026-10-17", "2026-10-18"))

    def test_hokkaido_invalid(self):
        self.assertIsNone(parse_dates("2026年2月31日", date(2026, 1, 1)))

    def test_hokkaido_older_year(self):
        self.assertIsNone(parse_dates("2025年10月17日", date(2026, 10, 10)))

    def test_no_dates(self):
        self.assertIsNone(_period("秋のイベント開催"))

    def test_invalid_date(self):
        self.assertIsNone(_period("2026年2月31日 マルシェ"))

if __name__ == "__main__":
    unittest.main()

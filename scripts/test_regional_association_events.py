"""Offline regression checks for association event date parsing."""
import unittest
from datetime import date
from regional_association_events import _period

class DateParsingTests(unittest.TestCase):
    def test_explicit_two_day(self):
        self.assertEqual(_period("開催期間 2026年10月17日～10月18日"),
                         ("2026-10-17", "2026-10-18"))

    def test_month_boundary(self):
        self.assertEqual(_period("10/30～11月3日 秋の洋らん展", date(2026, 10, 1)),
                         ("2026-10-30", "2026-11-03"))

    def test_no_dates(self):
        self.assertIsNone(_period("秋のイベント開催"))

    def test_invalid_date(self):
        self.assertIsNone(_period("2026年2月31日 マルシェ"))

if __name__ == "__main__":
    unittest.main()

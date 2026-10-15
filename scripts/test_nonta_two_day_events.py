"""Offline checks for Saijo Nonta two-day event evidence."""
import json
import unittest
from datetime import date
from pathlib import Path
from bs4 import BeautifulSoup
from station_discovery_engine import (
    _article_record, _event_title_year_two_day_period, _validate_sources, _plan_article_inspection
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = next(s for s in json.loads((ROOT / "data/station_event_discovery_sources.json").read_text(encoding="utf-8"))["sources"] if s["id"] == "hiroshima_nonta")

class NontaTwoDayTest(unittest.TestCase):
    def test_target_is_not_starved_by_ten_article_budget(self):
        links = {
            "https://www.nonta-sakagura.com/news/old" + str(i):
                "イベント 2026.09.13 過去の秋祭りお知らせ" + str(i)
            for i in range(12)
        }
        wanted = "https://www.nonta-sakagura.com/news/okomefes"
        links[wanted] = "イベント 2026.09.19 ぶちうまい！東広島お米フェス2026を開催いたします。"
        selected, info = _plan_article_inspection(links, SOURCE, date(2026,10,15))
        self.assertIn(wanted, selected)
        self.assertEqual(len(selected), 10)
        self.assertEqual(info["uninspectedCandidates"], 3)

    def test_source_valid(self):
        _validate_sources([SOURCE])

    def test_article_with_title_year_two_days(self):
        html = ('<main><h1>ぶちうまい！東広島お米フェス2026を開催いたします。</h1>'
                '<p>【日時】11月28日（土）29日（日）10時～15時</p>'
                '<p>【場所】道の駅西条のん太の酒蔵</p></main>')
        record, why = _article_record(SOURCE, BeautifulSoup(html, "html.parser"),
                                     "東広島お米フェス2026", date(2026, 10, 15),
                                     "https://www.nonta-sakagura.com/news/okomefes2026")
        self.assertIsNotNone(record, why)
        self.assertEqual(record["startDate"], "2026-11-28")
        self.assertEqual(record["endDate"], "2026-11-29")

    def test_no_year_no_inference(self):
        self.assertIsNone(_event_title_year_two_day_period(
            "お米フェス", ["日時：11月28日（土）29日（日）"], date(2026,10,15)))

    def test_reject_nonadjacent_days(self):
        self.assertIsNone(_event_title_year_two_day_period(
            "お米フェス2026", ["日時：11月28日（土）30日（月）"], date(2026,10,15)))

    def test_reject_other_station(self):
        html = '<main><h1>お米フェス2026開催</h1><p>日時：11月28日（土）29日（日）</p><p>場所：別会場</p></main>'
        record, _ = _article_record(SOURCE, BeautifulSoup(html, "html.parser"), "お米フェス2026", date(2026,10,15), "https://www.nonta-sakagura.com/news/okomefes")
        self.assertIsNone(record)

if __name__ == "__main__":
    unittest.main()

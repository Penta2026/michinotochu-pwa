"""Regression: Fukutomi source accepts only article-local dated events at station."""
import json
import unittest
from datetime import date
from pathlib import Path
from bs4 import BeautifulSoup
from station_discovery_engine import _article_record, _links, _validate_sources

ROOT=Path(__file__).resolve().parents[1]
SOURCE=next(s for s in json.loads((ROOT/"data/station_event_discovery_sources.json").read_text(encoding="utf-8"))["sources"] if s["id"]=="hiroshima_fukutomi")

class FukutomiTests(unittest.TestCase):
    def test_configuration_and_listing(self):
        _validate_sources([SOURCE])
        listing=BeautifulSoup('<a href="/news/retrocar-festa2026/">レトロカーフェスタ2026 エントリー開始！</a>',"html.parser")
        self.assertEqual(len(_links(listing,SOURCE)),1)
    def test_event_has_explicit_date_and_place(self):
        html='<main><h1>レトロカーフェスタ2026</h1><p>開催日時：2026年11月3日（火・祝）10:00〜15:00</p><p>開催場所：道の駅 湖畔の里福富 多目的グラウンド</p></main>'
        record,reason=_article_record(SOURCE,BeautifulSoup(html,"html.parser"),"レトロカーフェスタ2026",date(2026,10,15),"https://kohannosato.co.jp/news/retrocar-festa2026/")
        self.assertIsNotNone(record,reason)
        self.assertEqual(record["startDate"],"2026-11-03")
        self.assertEqual(record["roadName"],"湖畔の里福富")
    def test_year_from_event_title_and_month_day_from_body(self):
        html = '<main><h1>レトロカーフェスタ2026 エントリー開始！</h1><p>11月3日(火・祝)、道の駅湖畔の里福富にレトロな自動車が大集合するイベントを開催いたします。</p><p>参加募集</p></main>'
        record, reason = _article_record(SOURCE, BeautifulSoup(html, "html.parser"), "2026.09.23 レトロカーフェスタ2026 エントリー開始！", date(2026, 10, 15), "https://kohannosato.co.jp/news/retrocar-festa2026/")
        self.assertIsNotNone(record, reason)
        self.assertEqual(record["startDate"], "2026-11-03")
        self.assertEqual(record["endDate"], "2026-11-03")

    def test_reject_ambiguous_event_days(self):
        html = '<main><h1>レトロカーフェスタ2026</h1><p>11月3日に開催予定</p><p>11月4日にイベントを開催予定</p><p>道の駅湖畔の里福富</p></main>'
        record, _ = _article_record(SOURCE, BeautifulSoup(html, "html.parser"), "レトロカーフェスタ2026", date(2026, 10, 15), "https://kohannosato.co.jp/news/retrocar-festa2026/")
        self.assertIsNone(record)

    def test_post_date_is_not_event_date(self):
        html='<main><h1>レトロカーフェスタ2026 エントリー開始！</h1><p>2026年9月23日 更新</p><p>道の駅湖畔の里福富で開催予定</p></main>'
        record,_=_article_record(SOURCE,BeautifulSoup(html,"html.parser"),"レトロカーフェスタ2026",date(2026,10,15),"https://kohannosato.co.jp/news/retrocar-festa2026/")
        self.assertIsNone(record)
    def test_different_venue_rejected(self):
        html='<main><h1>レトロカーフェスタ2026</h1><p>開催日時：2026年11月3日</p><p>開催場所：別の公園</p></main>'
        record,_=_article_record(SOURCE,BeautifulSoup(html,"html.parser"),"レトロカーフェスタ2026",date(2026,10,15),"https://kohannosato.co.jp/news/retrocar-festa2026/")
        self.assertIsNone(record)
if __name__=="__main__": unittest.main()

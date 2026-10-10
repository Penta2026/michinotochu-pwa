"""Offline regression tests for official Kanto station-event adapters."""
import unittest
from datetime import date
from bs4 import BeautifulSoup
from kanto_three_prefectures import (
    parse_period, parse_ibaraki_prefecture, parse_showa_calendar,
    parse_mashiko_list, parse_kasama_list,
)
TODAY = date(2026, 10, 10)

class KantoThreeTests(unittest.TestCase):
    def test_ibaraki_2026_multi_venue_only_stations(self):
        soup = BeautifulSoup("""<main><h1>令和8年度ノウフクマルシェ</h1>
          <h3>第2回 ノウフクマルシェin道の駅ひたちおおた</h3>
          <p>日 時：令和８年１０月２４日（土）</p>
          <p>場 所：道の駅ひたちおおた テントドーム下</p>
          <h3>第3回 ノウフクマルシェin道の駅かさま</h3>
          <p>日時：令和8年11月21日（土）</p><p>場所：道の駅かさま 多目的広場</p>
          <h3>第4回 ノウフクマルシェin茨城県庁</h3>
          <p>日時：令和8年12月15日（火）</p>
          <p>場所：茨城県庁舎2階</p></main>""", "html.parser")
        got = parse_ibaraki_prefecture(soup, TODAY)
        self.assertEqual([(x["roadName"], x["startDate"]) for x in got],
                         [("ひたちおおた", "2026-10-24"),
                          ("かさま", "2026-11-21")])

    def test_ibaraki_previous_year_not_assumed_current(self):
        soup = BeautifulSoup("""<h3>第2回 ノウフクマルシェin道の駅ひたちおおた</h3>
          <p>日 時：令和7年10月25日（土）</p>
          <p>場 所：道の駅ひたちおおた</p>""", "html.parser")
        self.assertEqual(parse_ibaraki_prefecture(soup, TODAY), [])

    def test_mashiko_exact_event_day_not_promotion_dates(self):
        listing = BeautifulSoup("""<li>
          <a href="/event/4457/">〖event〗道の駅ましこ10周年祭</a>
          </li>""", "html.parser")
        detail = BeautifulSoup("""<main>
          <h1>〖event〗道の駅ましこ10周年祭</h1>
          <h2>〖開催日〗</h2><p>2026年10月11日（日）</p>
          <p>周年フェア期間 2026年10月10日～15日</p>
          </main>""", "html.parser")
        got, _ = parse_mashiko_list(listing, TODAY, fetch=lambda url: detail)
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0]["roadName"], got[0]["startDate"], got[0]["endDate"]),
                         ("ましこ", "2026-10-11", "2026-10-11"))

    def test_mashiko_related_dates_without_event_label_rejected(self):
        listing = BeautifulSoup("<li><a href='/event/4457/'>道の駅ましこ祭り</a></li>",
                                "html.parser")
        detail = BeautifulSoup("""<main><h1>道の駅ましこ祭り</h1>
          <p>定休日：2026年10月11日</p>
          <p>別イベント：2026年10月24日</p></main>""", "html.parser")
        got, _ = parse_mashiko_list(listing, TODAY, fetch=lambda url: detail)
        self.assertEqual(got, [])

    def test_showa_event_scoped_by_year_and_venue(self):
        soup = BeautifulSoup("""<h5>昭和の秋まつり</h5>
          <p>〖日時〗令和8年10月4日（日）</p>
          <p>〖場所〗昭和村総合福祉センター</p>
          <h5>道の駅・しょうわむらマルシェ</h5>
          <p>〖日時〗令和8年10月17日（土）〜18日（日）</p>
          <p>〖場所〗道の駅あぐりーむ昭和</p>
          <h5>道の駅・りんご足湯</h5>
          <p>〖日時〗令和8年10月10日（土）～12日（月）</p>
          <p>〖場所〗道の駅あぐりーむ昭和</p>""", "html.parser")
        got = parse_showa_calendar(soup, TODAY)
        self.assertEqual([(x["title"], x["startDate"], x["endDate"]) for x in got],
                         [("しょうわむらマルシェ", "2026-10-17", "2026-10-18"),
                          ("りんご足湯", "2026-10-10", "2026-10-12")])

    def test_showa_2025_archive_kept_out(self):
        soup = BeautifulSoup("""<h5>道の駅・しょうわむらマルシェ</h5>
          <p>〖日時〗令和7年10月11日（土）〜12日（日）</p>
          <p>〖場所〗道の駅あぐりーむ昭和</p>""", "html.parser")
        self.assertEqual(parse_showa_calendar(soup, TODAY), [])

    def test_kasama_year_from_same_list_entry(self):
        listing = BeautifulSoup("""<ul>
          <li><span>2026.09.23</span>
          <a href="/event-news1/">〖イベント〗10/24～25『ハロウィンマーケット』を開催します</a></li>
          <li><span>2025.09.23</span>
          <a href="/event-news2/">10/24～25『ハロウィンマーケット』</a></li>
          </ul>""", "html.parser")
        def get_detail(url):
            return BeautifulSoup("<main><h1>ハロウィンマーケット</h1></main>", "html.parser")
        got, candidate_count = parse_kasama_list(listing, TODAY, fetch=get_detail)
        self.assertEqual(candidate_count, 2)
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0]["startDate"], got[0]["endDate"]),
                         ("2026-10-24", "2026-10-25"))

    def test_date_ranges_require_year_and_validate_weekday(self):
        self.assertEqual(parse_period("令和8年10月10日(土)～12日(月)"),
                         ("2026-10-10", "2026-10-12"))
        self.assertEqual(parse_period("10/24・25", date(2026,9,23)),
                         ("2026-10-24", "2026-10-25"))
        self.assertIsNone(parse_period("10/24・25"))
        self.assertIsNone(parse_period("2026年10月24日(日)"))
        self.assertEqual(parse_period("令和7年10月17日(金)"),
                         ("2025-10-17", "2025-10-17"))

if __name__ == "__main__":
    unittest.main()

"""Offline regression tests for Chiba/Tokyo/Kanagawa station news collection."""
import unittest
from datetime import date
from bs4 import BeautifulSoup
from kanto_remaining_prefectures import (
    SOURCES, candidates, event_period, parse_one, article_event_period, _first_title,
)
TODAY=date(2026,10,10)

class KantoRemainingTests(unittest.TestCase):
    def test_three_prefectures_four_official_feeds(self):
        self.assertEqual({s["prefecture"] for s in SOURCES},
                         {"千葉県","東京都","神奈川県"})
        self.assertEqual({s["road"] for s in SOURCES},
                         {"しょうなん","保田小学校","八王子滝山","湘南ちがさき"})

    def test_shonan_station_photo_day(self):
        spec=SOURCES[0]
        soup=BeautifulSoup("""<article>
            <h1>10月10日 道の駅しょうなん「手賀沼フォトDAY」開催</h1>
            <p>道の駅しょうなんで「手賀沼フォトDAY」を開催します！</p>
            </article>""","html.parser")
        result,status=parse_one(spec,"",soup,date(2026,10,1),TODAY,
            "https://www.michinoeki-shonan.jp/news/3181/")
        self.assertEqual(status,"accepted")
        self.assertEqual((result["roadName"],result["startDate"],result["endDate"]),
                         ("しょうなん","2026-10-10","2026-10-10"))

    def test_shonan_river_path_offsite_is_excluded(self):
        soup=BeautifulSoup("""<article><h1>10月17日 「全国造園フェスティバル」開催</h1>
            <p>【開催日時】2026年10月17日(土)</p>
            <p>【開催場所】手賀沼自然ふれあい緑道</p>
            <p>道の駅しょうなんはクイズラリーのスポットとして参加</p>
            </article>""","html.parser")
        result,status=parse_one(SOURCES[0],"",soup,date(2026,10,8),TODAY,
          "https://www.michinoeki-shonan.jp/news/3170/")
        self.assertEqual((result,status),(None,"undated"))

    def test_shonan_recruitment_dates_not_events(self):
        soup=BeautifulSoup("""<article><h1>第3回料理コンテスト参加者募集</h1>
            <p>【応募受付期間】2026年10月1日～11月30日</p></article>""","html.parser")
        record,why=parse_one(SOURCES[0],"",soup,date(2026,9,25),TODAY,
          "https://www.michinoeki-shonan.jp/news/3144/")
        self.assertIsNone(record)
        self.assertEqual(why,"skipped")

    def test_chiba_hotasho_event_title_dotted_date(self):
        title="保田小附属ようちえん3周年開園祭（2026.10.10～12）"
        soup=BeautifulSoup("<main><h1>"+title+"</h1><p>3周年開園祭を開催!</p></main>",
                           "html.parser")
        record,status=parse_one(SOURCES[1],title,soup,date(2026,9,6),TODAY,
                                 "https://hotasho.jp/sanniversary/")
        self.assertEqual(status,"accepted")
        self.assertEqual((record["roadName"],record["startDate"],record["endDate"]),
                         ("保田小学校","2026-10-10","2026-10-12"))

    def test_hotasho_recruitment_deadline_not_celebration(self):
        title="遊具の名前を募集します！"
        soup=BeautifulSoup("<h1>"+title+"</h1><p>10月3日必着</p>", "html.parser")
        record,status=parse_one(SOURCES[1],title,soup,date(2026,9,16),TODAY,
                               "https://hotasho.jp/toy-name/")
        self.assertEqual((record,status),(None,"skipped"))

    def test_tokyo_image_only_schedule_has_no_inferred_range(self):
        title="10月分イベントスケジュールです"
        soup=BeautifulSoup("<article><h1>"+title+"</h1>"
                           "<img src='calendar202610.png' alt='10月の予定'></article>",
                           "html.parser")
        record,status=parse_one(SOURCES[2],title,soup,date(2026,10,9),TODAY,
                                "https://www.michinoeki-hachioji.net/news/931")
        self.assertEqual((record,status),(None,"undated"))

    def test_tokyo_dated_individual_exhibition(self):
        title="台湾フェアを開催！"
        soup=BeautifulSoup("""<article><h1>台湾フェアを開催！</h1>
            <p>日時：2026年11月25日（水）～2026年11月27日（金）</p></article>""",
            "html.parser")
        record,status=parse_one(SOURCES[2],title,soup,date(2026,11,20),
                                date(2026,11,20),
                                "https://www.michinoeki-hachioji.net/news/2000")
        self.assertEqual(status,"accepted")
        self.assertEqual((record["startDate"],record["endDate"]),
                         ("2026-11-25","2026-11-27"))

    def test_kanagawa_monthly_image_calendar_is_not_event(self):
        title="10月イベントカレンダー"
        soup=BeautifulSoup("<article><h1>"+title+"</h1>"
                           "<img src='2026-10-event.jpg'></article>","html.parser")
        record,status=parse_one(SOURCES[3],title,soup,date(2026,9,28),TODAY,
                         "https://m-shonanchigasaki.com/topics/detail.php?id=114")
        self.assertEqual((record,status),(None,"undated"))

    def test_kanagawa_future_dated_fair_is_eligible(self):
        title="沖縄フェア開催！"
        soup=BeautifulSoup("""<article><h1>沖縄フェア開催！</h1>
            <p>開催日時：2026年10月24日（土）～25日（日）</p>
            </article>""","html.parser")
        record,status=parse_one(SOURCES[3],title,soup,date(2026,10,8),TODAY,
               "https://m-shonanchigasaki.com/topics/detail.php?id=999")
        self.assertEqual(status,"accepted")
        self.assertEqual((record["startDate"],record["endDate"]),
                         ("2026-10-24","2026-10-25"))

    def test_year_and_weekday_must_be_grounded(self):
        self.assertIsNone(event_period("10月17日（土）"))
        self.assertIsNone(event_period("2025.10.17～18",None) if False else
                          event_period("2026年10月17日（日）"))
        self.assertEqual(event_period("10月17日(土)",date(2026,10,8)),
                         ("2026-10-17","2026-10-17"))

    def test_official_link_hosts_only(self):
        html="""<a href="https://evil.example/news/99/">10月24日 まつり</a>
         <a href="/news/3181/">10月10日 手賀沼フォトDAY</a>
         <a href="/news/3144/">料理コンテスト参加者募集</a>"""
        links=candidates(SOURCES[0],BeautifulSoup(html,"html.parser"))
        self.assertIn("https://www.michinoeki-shonan.jp/news/3181/",links)
        self.assertNotIn("https://evil.example/news/99/",links)
        self.assertNotIn("https://www.michinoeki-shonan.jp/news/3144/",links)

if __name__=="__main__":
    unittest.main()

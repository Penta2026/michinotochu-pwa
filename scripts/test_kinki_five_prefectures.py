"""Offline safety checks for 5 Kinki prefecture station event sources."""
import unittest
from datetime import date
from bs4 import BeautifulSoup
from kinki_five_prefectures import (
    SOURCES, event_period, _article_date, _candidates, _venue_ok
)

TODAY=date(2026,10,10)
class KinkiFiveTests(unittest.TestCase):
    def test_all_five_prefectures_configured(self):
        self.assertEqual(set(x["prefecture"] for x in SOURCES),
                         {"福井県","京都府","大阪府","奈良県","和歌山県"})

    def test_kyoto_wachi_october_2026_fair(self):
        p=event_period("黒大豆枝豆もぎとり収穫体験 (2026年10月16日〜11月3日)")
        self.assertEqual(p,("2026-10-16","2026-11-03"))

    def test_kyoto_october_weekday_title_from_publication(self):
        p=event_period("10/11（日）いととめのぼたもち実演販売",date(2026,9,28))
        self.assertEqual(p,("2026-10-11","2026-10-11"))
        self.assertIsNone(event_period("10/11（日）いととめのぼたもち実演販売"))

    def test_nara_october_new_show(self):
        self.assertEqual(event_period("10/31（土）まほろばの宴",date(2026,10,6)),
                         ("2026-10-31","2026-10-31"))

    def test_nara_2025_archived_not_reyear(self):
        p=event_period("11/29（土）開駅1周年記念フェア",date(2025,11,27))
        self.assertEqual(p,("2025-11-29","2025-11-29"))
        self.assertLess(p[1],TODAY.isoformat())

    def test_fukui_mihama_past_notice_not_2026_future(self):
        p=event_period("9月27日(日) 2026 はまびより音楽祭",
                       date(2026,9,2))
        self.assertEqual(p,("2026-09-27","2026-09-27"))
        self.assertLess(p[1],TODAY.isoformat())

    def test_kinki_exclude_cancellation_and_recruitment(self):
        spec=SOURCES[2]
        soup=BeautifulSoup("""<article>
          <a href="/event/901/">黒枝豆収穫体験 開催中止についてのお知らせ</a>
          <a href="/event/902/">あんマルシェ2026 開催のご案内</a>
          <a href="https://evil.example/event/903/">イベント開催</a></article>""",
          "html.parser")
        links=_candidates(spec,soup)
        self.assertEqual(list(links),["https://ajim.info/event/902/"])

    def test_nara_date_in_labelled_body(self):
        spec=SOURCES[4]
        soup=BeautifulSoup("""<article><h1>日本伝統芸能猿まわし開催</h1>
           <p>開催日：2026年10月11日（日）</p></article>""",
           "html.parser")
        self.assertEqual(_article_date(spec,"猿まわし開催",soup,date(2026,10,1)),
                         ("2026-10-11","2026-10-11"))

    def test_wakayama_month_only_never_becomes_monthlong_event(self):
        spec=SOURCES[5]
        soup=BeautifulSoup("""<article><h1>10月イベントカレンダー</h1>
            <p>イベントの案内です</p></article>""","html.parser")
        self.assertIsNone(_article_date(spec,"10月イベントカレンダー",
                                        soup,date(2026,10,1)))

    def test_osaka_different_venue_not_station(self):
        spec=SOURCES[3]
        offsite=BeautifulSoup("""<article><h1>里山マルシェ開催</h1>
            <p>開催場所：和泉市役所会議室</p></article>""","html.parser")
        onsite=BeautifulSoup("""<article><h1>里山マルシェ開催</h1>
            <p>会場：南部リージョンセンター芝生広場</p></article>""","html.parser")
        self.assertFalse(_venue_ok(spec,"里山マルシェ開催",offsite))
        self.assertTrue(_venue_ok(spec,"里山マルシェ開催",onsite))

    def test_invalid_weekday_cannot_be_published(self):
        self.assertIsNone(event_period("2026年10月11日（土）"))
        self.assertIsNone(event_period("2026年2月30日"))
        self.assertIsNone(event_period("11月14日（土）"))

if __name__=="__main__":
    unittest.main()

"""Offline regression checks for association event date parsing."""
import unittest
from datetime import date
from regional_association_events import _period
from region_official_events import _murata_period
from generic_region_events import period as generic_period
from collect_road_events import chugoku_period
from hokkaido_events import parse_dates
from kanto_events import event_period
from chubu_events import bulletin_links, bulletin_date, verified_pdf_events

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

    def test_kanto_date_from_published(self):
        self.assertEqual(event_period("日時：10月31日(土)～11月1日(日)", date(2026,9,30)),
                         ("2026-10-31","2026-11-01"))

    def test_kanto_explicit_year(self):
        self.assertEqual(event_period("2026年10月24日(土)",date(2026,10,1)),
                         ("2026-10-24","2026-10-24"))

    def test_chubu_bulletin_discovery(self):
        html = '<a href="/pdf/20260901event_vol103.pdf">中部イベント情報</a>'
        self.assertEqual(bulletin_links(html, "https://www.chubu-michinoeki.org/"),
                         ["https://www.chubu-michinoeki.org/pdf/20260901event_vol103.pdf"])

    def test_chubu_ignore_external_bulletin(self):
        html = '<a href="https://example.com/event.pdf">中部イベント情報</a>'
        self.assertEqual(bulletin_links(html, "https://www.chubu-michinoeki.org/"), [])

    def test_chubu_bulletin_date_range(self):
        self.assertEqual(bulletin_date("●10月10日㈯〜12日（月・祝） 収穫祭", 2026),
                         ("2026-10-10", "2026-10-12"))

    def test_chubu_middle_dot_two_days(self):
        self.assertEqual(bulletin_date("●10月24日(土)・25日(日) 飯高駅 感謝祭", 2026),
                         ("2026-10-24", "2026-10-25"))

    def test_chubu_reject_end_only(self):
        self.assertIsNone(bulletin_date("●~11月30日(月) NWR166スタンプラリー", 2026))
        self.assertIsNone(bulletin_date("●～11月17日(火) 【展示】", 2026))

    def test_chubu_verified_station(self):
        report={"source":"https://www.chubu-michinoeki.org/pdf/test.pdf",
                "pages":[{"rows":[
                    {"x":44,"y":10,"text":"〈2 0 26 年〉10月","section":"left_station"},
                    {"x":41,"y":72,"text":"❾信州新野千石平","section":"left_station"},
                    {"x":162,"y":74,"text":"●10月10日㈯〜12日（月・祝） 信州新野千石平 道の駅【収穫祭】","section":"left_station_event"},
                    {"x":414,"y":74,"text":"▼10月10日㈯ 周辺地域イベント","section":"left_nearby"}
                ]}]}
        records=verified_pdf_events(report,date(2026,10,10))
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]["roadName"],"信州新野千石平")

    def test_chubu_station_position(self):
        report={"source":"https://www.chubu-michinoeki.org/pdf/test.pdf",
                "pages":[{"rows":[
                    {"x":44,"y":10,"text":"〈2 0 26 年〉10月","section":"left_station"},
                    {"x":41,"y":425,"text":"⤪古今伝授の里やまと","section":"left_station"},
                    {"x":162,"y":435,"text":"●10月17日㈯・18日㈰ とんぼ玉販売","section":"left_station_event"},
                    {"x":41,"y":485,"text":"㊺柳津","section":"left_station"},
                    {"x":162,"y":496,"text":"●10月25日㈰ Yanaizuマルシェ","section":"left_station_event"},
                    {"x":414,"y":496,"text":"▼10月25日㈰ 周辺イベント","section":"left_nearby"}
                ]}]}
        got=verified_pdf_events(report,date(2026,10,10))
        self.assertEqual([(x["roadName"],x["endDate"]) for x in got],
                         [("古今伝授の里やまと","2026-10-18"),("柳津","2026-10-25")])

    def test_no_dates(self):
        self.assertIsNone(_period("秋のイベント開催"))

    def test_invalid_date(self):
        self.assertIsNone(_period("2026年2月31日 マルシェ"))

if __name__ == "__main__":
    unittest.main()

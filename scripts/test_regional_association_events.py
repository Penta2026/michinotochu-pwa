"""Offline regression checks for association event date parsing."""
import unittest
from datetime import date
from regional_association_events import _period, _kinki_station_title
from region_official_events import _murata_period
from generic_region_events import period as generic_period
from collect_road_events import chugoku_period, EVENT_WORDS
from hokkaido_events import parse_dates
from hokuriku_events import extract_hokuriku, extract_hokuriku_cards, decode_official_response, extract_rendered_events
from bs4 import BeautifulSoup
from kanto_events import event_period
from chubu_events import bulletin_links, bulletin_date, verified_pdf_events
from road_event_quality import reconcile

class DateParsingTests(unittest.TestCase):
    def test_explicit_two_day(self):
        self.assertEqual(_period("開催期間 2026年10月17日～10月18日"),
                         ("2026-10-17", "2026-10-18"))

    def test_kinki_quoted_station_title(self):
        self.assertEqual(_kinki_station_title("「道の駅 奥永源寺渓流の里」開駅１１周年記念祭を開催します。"),
                         "奥永源寺渓流の里")
        self.assertEqual(_kinki_station_title("【道の駅クロスウェイなかまち】夜市開催"),
                         "クロスウェイなかまち")
        self.assertIsNone(_kinki_station_title("道の駅まつり開催"))

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

    def test_chugoku_festa_is_event_word(self):
        self.assertTrue(any(word in "第６回 秋わくわくフェスタ" for word in EVENT_WORDS))

    def test_chugoku_tonbara_festival(self):
        self.assertEqual(
            chugoku_period("第６回 秋わくわくフェスタ 10月24日（土）10時から15時",
                           date(2026,9,25)),
            ("2026-10-24","2026-10-24"))

    def test_chugoku_multiple_dates(self):
        self.assertEqual(chugoku_period("秋の祭 10月17日(土)～10月18日(日)", date(2026, 10, 1)),
                         ("2026-10-17", "2026-10-18"))

    def test_chugoku_old_year(self):
        self.assertIsNone(chugoku_period("秋祭り 2025年10月24日", date(2025, 10, 1)))

    def test_hokkaido_takikawa_two_days(self):
        self.assertEqual(parse_dates("2026年10月17日、18日", date(2026, 10, 10)),
                         ("2026-10-17", "2026-10-18"))

    def test_hokkaido_short_date_requires_context(self):
        self.assertEqual(parse_dates("10月11日(日) 道の駅フェスト",date(2026,10,10),allow_short=True),
                         ("2026-10-11","2026-10-11"))
        self.assertIsNone(parse_dates("10月11日(日) 道の駅フェスト",date(2026,10,10)))

    def test_hokkaido_invalid(self):
        self.assertIsNone(parse_dates("2026年2月31日", date(2026, 1, 1)))

    def test_hokkaido_older_year(self):
        self.assertIsNone(parse_dates("2025年10月17日", date(2026, 10, 10)))

    def test_hokuriku_calendar_entry(self):
        text="2026年10月10土 氷見2026年10月3日2026年10月12日ひみ番屋街創業14周年感謝祭"
        event=extract_hokuriku(text,date(2026,10,10),"https://www.hokuriku-michinoeki.jp/contents/event/")
        self.assertEqual((event["roadName"],event["startDate"],event["endDate"]),
                         ("氷見","2026-10-03","2026-10-12"))

    def test_hokuriku_dates_in_card_siblings(self):
        html = '''<div class="event-card"><span>氷見</span>
          <span>2026年10月3日</span><span>2026年10月12日</span>
          <a href="/contents/event/?article=000900&dc=2026-10-10">ひみ番屋街創業14周年感謝祭</a>
          </div>'''
        soup = BeautifulSoup(html, "html.parser")
        records, stats = extract_hokuriku_cards(
            soup, date(2026, 10, 10),
            "https://www.hokuriku-michinoeki.jp/contents/event/?dc=2026-10-10")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["roadName"], "氷見")
        self.assertEqual(records[0]["title"], "ひみ番屋街創業14周年感謝祭")
        self.assertEqual(records[0]["endDate"], "2026-10-12")
        self.assertEqual(stats["articleLinks"], 1)

    def test_hokuriku_reject_nav_near_event(self):
        html = '''<div><span>氷見 2026年10月3日 2026年10月12日 感謝祭</span>
          <a href="/contents/event/?dc=2026-10-17">翌週へ</a></div>'''
        records, _ = extract_hokuriku_cards(
            BeautifulSoup(html, "html.parser"), date(2026,10,10),
            "https://www.hokuriku-michinoeki.jp/contents/event/")
        self.assertEqual(records, [])

    def test_hokuriku_decoding_without_charset(self):
        class FakeResponse:
            content = "氷見2026年10月3日2026年10月12日感謝祭".encode("utf-8")
            encoding = "ISO-8859-1"
            apparent_encoding = "utf-8"
        self.assertIn("氷見", decode_official_response(FakeResponse()))

    def test_hokuriku_prevent_cross_card(self):
        html = """<div><span>氷見2026年10月3日2026年10月12日感謝祭</span>
          <span>めぐみ白山2026年10月25日2026年10月25日フェア</span>
          <a href="/contents/event/?article=000900&dc=2026-10-10">詳細</a></div>"""
        records, _ = extract_hokuriku_cards(
            BeautifulSoup(html,"html.parser"),date(2026,10,10),
            "https://www.hokuriku-michinoeki.jp/contents/event/")
        self.assertEqual(records, [])

    def test_hokuriku_browser_rendered_card(self):
        html = """<div><div class="event">
          <span>氷見</span><span>2026年10月3日</span>
          <span>2026年10月12日</span>
          <a href="/contents/event/?article=9001">ひみ番屋街創業14周年感謝祭</a>
          </div></div>"""
        events = extract_rendered_events(
            BeautifulSoup(html, "html.parser"), date(2026, 10, 10),
            "https://www.hokuriku-michinoeki.jp/contents/event/")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["roadName"], "氷見")
        self.assertEqual(events[0]["startDate"], "2026-10-03")
        self.assertEqual(events[0]["endDate"], "2026-10-12")
        self.assertIn("article=9001", events[0]["url"])

    def test_hokuriku_browser_does_not_cross_event_cards(self):
        html = """<div><div class="event">
            氷見 2026年10月3日
          </div><div class="event">
            めぐみ白山 2026年10月25日 白山道の駅フェア
          </div></div>"""
        events = extract_rendered_events(
            BeautifulSoup(html, "html.parser"), date(2026, 10, 10),
            "https://www.hokuriku-michinoeki.jp/contents/event/")
        self.assertEqual(events, [])

    def test_hokuriku_reject_past(self):
        text="氷見2026年9月3日2026年9月12日過去の感謝祭"
        self.assertIsNone(extract_hokuriku(text,date(2026,10,10),"https://www.hokuriku-michinoeki.jp/"))

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

    def test_chubu_weekday_mismatch(self):
        self.assertIsNone(bulletin_date("●10月24日(日) 感謝祭", 2026))
        self.assertIsNone(bulletin_date("●10月24日(土)・25日(土) 感謝祭", 2026))

    def test_chubu_station_boundary(self):
        report={"source":"https://www.chubu-michinoeki.org/pdf/test.pdf",
                "pages":[{"rows":[
                    {"x":44,"y":10,"text":"〈2 0 26 年〉10月","section":"left_station"},
                    {"x":41,"y":300,"text":"⤪古今伝授の里やまと","section":"left_station"},
                    {"x":162,"y":342,"text":"●10月24日(土) 催し","section":"left_station_event"},
                    {"x":41,"y":350,"text":"㊺柳津","section":"left_station"}
                ]}]}
        self.assertEqual([e["roadName"] for e in verified_pdf_events(report,date(2026,10,10))],
                         ["古今伝授の里やまと"])

    def test_chubu_long_station_event_sections(self):
        report={"source":"https://www.chubu-michinoeki.org/pdf/test.pdf",
                "pages":[{"rows":[
                    {"x":44,"y":10,"text":"〈2 0 26 年〉10月","section":"left_station"},
                    {"x":41,"y":425,"text":"⤪古今伝授の里やまと","section":"left_station"},
                    {"x":162,"y":463.2,"text":"●10月31日㈯〜11月3日（火・祝） 感謝祭","section":"left_station_event"},
                    {"x":41,"y":485.5,"text":"㊺柳津","section":"left_station"},
                    {"x":636,"y":516.8,"text":"❶飯高駅","section":"right_station"},
                    {"x":757,"y":580.4,"text":"●10月29日㈭～11月24日㈫ 【展示】田中三津子 人形展","section":"right_station_event"},
                    {"x":636,"y":618,"text":"❻奥伊勢木つつ木館","section":"right_station"}
                ]}]}
        got=verified_pdf_events(report,date(2026,10,10))
        self.assertEqual({e["roadName"] for e in got},{"古今伝授の里やまと","飯高駅"})

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

    def test_reconcile_date_correction_without_duplicate(self):
        base={"url":"https://official.example/events/1","roadName":"飯高駅",
              "prefecture":"三重県","title":"感謝祭","startDate":"2026-10-24",
              "endDate":"2026-10-24","status":"scheduled"}
        newer=dict(base,endDate="2026-10-25")
        records, audit=reconcile([base],[newer],date(2026,10,10))
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]["endDate"],"2026-10-25")
        self.assertEqual(len(audit["corrected"]),1)

    def test_reconcile_distinct_same_day_events(self):
        base={"url":"https://official.example/bulletin.pdf","roadName":"飯高駅",
              "prefecture":"三重県","startDate":"2026-10-24",
              "endDate":"2026-10-25","status":"scheduled"}
        events=[dict(base,title="感謝祭"),dict(base,title="展示会")]
        result,_=reconcile([],events,date(2026,10,10))
        self.assertEqual(len(result),2)

    def test_reconcile_cross_source_kept_for_review(self):
        base={"url":"https://official.example/a","roadName":"飯高駅",
              "prefecture":"三重県","title":"感謝祭",
              "startDate":"2026-10-24","endDate":"2026-10-25"}
        others=[base,dict(base,url="https://official.example/b")]
        result,audit=reconcile([],others,date(2026,10,10))
        self.assertEqual(len(result),2)
        self.assertEqual(len(audit["possibleDuplicates"]),1)

    def test_reconcile_same_title_different_days(self):
        base={"url":"https://official.example/a","roadName":"飯高駅",
              "title":"朝市","startDate":"2026-10-11","endDate":"2026-10-11"}
        later=dict(base,startDate="2026-10-18",endDate="2026-10-18")
        records,audit=reconcile([base],[later],date(2026,10,10))
        self.assertEqual(len(records),2)
        self.assertEqual(len(audit["corrected"]),0)

    def test_reconcile_reports_unconfirmed(self):
        base={"url":"https://official.example/a","roadName":"飯高駅",
              "title":"感謝祭","startDate":"2026-10-24","endDate":"2026-10-25"}
        other=dict(base,title="展示会")
        records,audit=reconcile([base,other],[base],date(2026,10,10))
        self.assertEqual(len(records),2)
        self.assertEqual([x["title"] for x in audit["notReconfirmed"]],["展示会"])

    def test_no_dates(self):
        self.assertIsNone(_period("秋のイベント開催"))

    def test_invalid_date(self):
        self.assertIsNone(_period("2026年2月31日 マルシェ"))

if __name__ == "__main__":
    unittest.main()

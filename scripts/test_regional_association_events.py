"""Offline regression checks for association event date parsing."""
import unittest
from datetime import date
from regional_association_events import _period, _kinki_station_title
from region_official_events import _murata_period
from generic_region_events import period as generic_period
from collect_road_events import chugoku_period, EVENT_WORDS
from hokkaido_events import parse_dates, _station_sentence_period, _posted_year_for_notice
from kyushu_six_prefectures import explicit_event_period as six_period, event_date_from_official_article as six_article_period, _candidate_links as six_candidate_links, SOURCES as SIX_PREFECTURE_SOURCES
from kyushu_okinawa_events import event_period as kyushu_event_period, publication_date as kyushu_publication_date, article_event_period as kyushu_article_event_period, _article_candidates as kyushu_article_candidates, SOURCES as KYUSHU_SOURCES, kadena_explicit_venue_period
from hokuriku_events import extract_hokuriku, extract_hokuriku_cards, decode_official_response, extract_rendered_events
from bs4 import BeautifulSoup
from kanto_events import event_period
from chubu_events import bulletin_links, bulletin_date, verified_pdf_events
from road_event_quality import reconcile, coalesce_hokuriku_records

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

    def test_six_kumamoto_2026_night_market(self):
        self.assertEqual(six_period("2026年10月24日(土)第8回ハッピー夜市"),
                         ("2026-10-24", "2026-10-24"))

    def test_six_oita_reiwa_lantern_dates(self):
        self.assertEqual(six_period("令和8年10月10日土曜日〜12日月曜日 17時～20時"),
                         ("2026-10-10", "2026-10-12"))

    def test_six_oita_full_year_with_parenthetical_weekday(self):
        self.assertEqual(six_period("2026年10月10日(土)～12日(月・祝)"),
                         ("2026-10-10", "2026-10-12"))

    def test_six_miyazaki_r8_kitchen_class(self):
        self.assertEqual(six_period("R8 11月10日(火) 秋の蕎麦打ち体験"),
                         ("2026-11-10", "2026-11-10"))

    def test_six_unknown_start_rejected(self):
        self.assertIsNone(six_period("期間:～10月31日(土)", date(2026,10,9)))
        self.assertIsNone(six_period("秋の収穫祭"))
        self.assertIsNone(six_period("2026年10月24日(日) 夜市"))

    def test_six_saga_article_date_not_post_date(self):
        html = """<article><h1>秋の収穫祭</h1>
          <div class="post-date">2026年10月8日</div>
          <div class="entry-content"><p>開催日：2026年10月18日（日）</p>
          <p>会場：道の駅しろいし</p></div></article>"""
        soup = BeautifulSoup(html, "html.parser")
        self.assertEqual(six_article_period("秋の収穫祭", soup, date(2026,10,8)),
                         ("2026-10-18", "2026-10-18"))

    def test_six_oita_avoids_nonstation_festival(self):
        spec = SIX_PREFECTURE_SOURCES[3]
        html = """<a href="/events/detail/100">吉野ヶ里ふるさと炎まつり</a>
          <a href="/events/detail/13635">道の駅耶馬トピア 竹の千灯籠夜</a>"""
        candidates = six_candidate_links( spec,
            BeautifulSoup(html, "html.parser"), spec["list"])
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0][1], "道の駅耶馬トピア 竹の千灯籠夜")
        self.assertEqual(candidates[1][0], "https://www.city-nakatsu.jp/doc/2026100500057/")

    def test_six_skip_recruitment(self):
        spec = SIX_PREFECTURE_SOURCES[4]
        html = """<a href="/recruit/">令和8年12月ニクルの朝市 出店募集！！</a>
          <a href="/class/">11月 秋の蕎麦打ち体験 開催</a>"""
        candidates = six_candidate_links(
            spec, BeautifulSoup(html, "html.parser"), spec["list"])
        self.assertEqual(len(candidates), 1)
        self.assertIn("/class/", candidates[0][0])

    def test_hokkaido_hidaka_official_prose_2026(self):
        soup = BeautifulSoup("""<article>
        <h1>日高町道の駅フェスト開催のお知らせ</h1>
        <div>2026年10月7日</div>
        <p>10月11日（日）道の駅樹海ロード日高入り口前にて
        「日高町道の駅フェスト」を開催します。</p>
        </article>""", "html.parser")
        title = "日高町道の駅フェスト開催のお知らせ"
        self.assertEqual(_posted_year_for_notice(soup, title), date(2026, 10, 7))
        self.assertEqual(_station_sentence_period(
            soup, title, "樹海ロード日高", date(2026, 10, 10)),
            ("2026-10-11", "2026-10-11"))

    def test_hokkaido_does_not_reyear_old_event(self):
        soup = BeautifulSoup("""<article>
        <h1>日高町道の駅フェスト開催のお知らせ</h1>
        <div>2025年10月7日</div>
        <p>10月11日（土）道の駅樹海ロード日高で
        「日高町道の駅フェスト」を開催します。</p>
        </article>""", "html.parser")
        self.assertIsNone(_station_sentence_period(
            soup, "日高町道の駅フェスト開催のお知らせ",
            "樹海ロード日高", date(2026, 10, 10)))

    def test_hokkaido_no_standalone_year_rejected(self):
        soup = BeautifulSoup("""<article>
        <h1>日高町道の駅フェスト開催のお知らせ</h1>
        <p>10月11日(日)道の駅樹海ロード日高で祭りを開催</p>
        </article>""", "html.parser")
        self.assertIsNone(_station_sentence_period(
            soup, "日高町道の駅フェスト開催のお知らせ",
            "樹海ロード日高", date(2026, 10, 10)))

    def test_kyushu_kurume_new_rice_fair(self):
        soup = BeautifulSoup('''<html><article><header><time datetime="2026-10-09">2026年10月9日</time></header>
            <div class="entry-content"><p>【新米フェア開催のお知らせ】</p>
            <p>場所：農産物直売館内</p><p>期間：１０月１７日（土）▶１１月３日（火）</p>
            </div></article></html>''', "html.parser")
        published = kyushu_publication_date(soup)
        self.assertEqual(published, date(2026, 10, 9))
        self.assertEqual(kyushu_article_event_period(
            soup, "【イベント情報】新米フェアのお知らせ", published),
            ("2026-10-17", "2026-11-03"))

    def test_kyushu_kurume_span_only_article_period(self):
        # On the live station page the labelled period can be text split
        # across span/br elements rather than a <p> line.
        soup = BeautifulSoup("""<article><header><time datetime="2026-10-09">
          2026年10月9日</time></header>
          <div class="entry-content">
            <strong>【新米フェア開催のお知らせ】</strong>
            <span>場所：農産物直売館内</span><br>
            <span>期間：</span><span>10月17日( 土 )</span><span>▶</span>
            <span>11月3日(火)</span>
            <div>新米はもちろん、新米と一緒におすすめの加工品を集めたコーナーを設置します!</div>
          </div></article>""", "html.parser")
        published = kyushu_publication_date(soup)
        self.assertEqual(kyushu_article_event_period(
            soup, "【イベント情報】新米フェアのお知らせ", published),
            ("2026-10-17", "2026-11-03"))

    def test_kyushu_end_only_span_not_inferred(self):
        soup = BeautifulSoup("""<article><div class="entry-content">
          <span>場所：農産物直売館内</span><span>期間：</span>
          <span>～10月31日(土)まで</span>
          </div></article>""", "html.parser")
        self.assertIsNone(kyushu_article_event_period(
            soup, "【イベント情報】きのこフェアのお知らせ", date(2026, 10, 8)))

    def test_kyushu_publication_date_next_to_article_title(self):
        soup = BeautifulSoup("""<div class="article-main">
           <h1>【イベント情報】新米フェアのお知らせ</h1>
           <div>2026年10月9日</div>
           <section class="entry-content">
             <p>場所：農産物直売館内</p>
             <p>期間：１０月１７日（土）▶１１月３日（火）</p>
           </section>
         </div>""", "html.parser")
        published = kyushu_publication_date(soup, "【イベント情報】新米フェアのお知らせ")
        self.assertEqual(published, date(2026, 10, 9))
        self.assertEqual(kyushu_article_event_period(
            soup, "【イベント情報】新米フェアのお知らせ", published),
            ("2026-10-17", "2026-11-03"))

    def test_okinawa_publication_date_next_to_article_title(self):
        title = "9月27日(日) チャレンジステーション@道の駅かでな開催"
        soup = BeautifulSoup("<main><h1>" + title + "</h1><div>2026年09月22日</div>"
                             "<p>9月27日(日) 道の駅かでなにて開催</p></main>",
                             "html.parser")
        self.assertEqual(kyushu_publication_date(soup, title), date(2026, 9, 22))

    def test_kyushu_publication_not_taken_from_unrelated_page(self):
        soup = BeautifulSoup("""<h1>新米フェアのお知らせ</h1><p>期間：10月17日(土)</p>
          <footer><h2>その他のお知らせ</h2><time>2026年10月9日</time></footer>""",
          "html.parser")
        self.assertIsNone(kyushu_publication_date(soup, "新米フェアのお知らせ"))

    def test_kyushu_publication_ignores_footer_inside_article(self):
        title = "新米フェアのお知らせ"
        soup = BeautifulSoup("""<article><h1>新米フェアのお知らせ</h1>
          <p>開催期間：10月17日（土）～11月3日（火）</p>
          <footer><time datetime="2026-10-09">2026年10月9日</time></footer>
          </article>""", "html.parser")
        self.assertIsNone(kyushu_publication_date(soup, title))

    def test_kyushu_publication_ignores_unrelated_news_widget(self):
        title = "新米フェアのお知らせ"
        soup = BeautifulSoup("""<main><article>
          <h1>新米フェアのお知らせ</h1>
          <p>開催期間：10月17日（土）～11月3日（火）</p></article>
          <aside><div class="post-date">2026年10月9日</div></aside>
          </main>""", "html.parser")
        self.assertIsNone(kyushu_publication_date(soup, title))

    def test_kadena_unlabelled_event_sentence(self):
        title = "月眺みぬ会開催のお知らせ"
        html = """<html><body><h1>""" + title + """</h1>
          <div>2026年09月06日</div>
          <div>10月17日 (土) は道の駅かでなにて 月眺みぬ会が開催されます。</div>
          <h2>その他お知らせ</h2><div>2026年10月23日 新しいお知らせ</div>
          </body></html>"""
        soup = BeautifulSoup(html, "html.parser")
        self.assertEqual(
            kadena_explicit_venue_period(soup, title, date(2026, 9, 6)),
            ("2026-10-17", "2026-10-17"))

    def test_kadena_related_notice_must_not_be_event(self):
        title = "月眺みぬ会開催のお知らせ"
        html = """<html><body><h1>""" + title + """</h1>
          <div>2026年09月06日</div><p>開催についてのお知らせです。</p>
          <h2>その他お知らせ</h2>
          <p>10月17日(土)は道の駅かでなにて 月眺みぬ会が開催されます。</p>
          </body></html>"""
        self.assertIsNone(kadena_explicit_venue_period(
            BeautifulSoup(html, "html.parser"), title, date(2026, 9, 6)))

    def test_kadena_invalid_weekday_rejected(self):
        title = "月眺みぬ会開催のお知らせ"
        html = """<h1>""" + title + """</h1>
        <div>2026年09月06日</div><p>10月17日 (日) は道の駅かでなにて
        月眺みぬ会が開催されます。</p>"""
        self.assertIsNone(kadena_explicit_venue_period(
            BeautifulSoup(html, "html.parser"), title, date(2026, 9, 6)))

    def test_kyushu_reject_end_only_and_publication_date(self):
        posted = date(2026, 10, 8)
        self.assertIsNone(kyushu_event_period("期間：～１０月３１日(土)まで", posted))
        self.assertIsNone(kyushu_event_period("食欲の秋！きのこフェアのお知らせ", posted))

    def test_okinawa_kadena_published_date_is_not_event(self):
        posted = date(2026, 9, 22)
        self.assertEqual(kyushu_event_period(
            "9月27日（日） チャレンジステーション@道の駅かでな開催", posted),
            ("2026-09-27", "2026-09-27"))
        self.assertIsNone(kyushu_event_period("10月26日（日）チャレンジステーション", posted))

    def test_kyushu_listing_ignores_monthly_multi_event_and_external(self):
        html = '''<article><h2><a href="/shinmaifair/">【イベント情報】新米フェアのお知らせ</a></h2></article>
            <article><h2><a href="/10gatuno-event/">10月のイベント情報［2026］</a></h2></article>
            <article><h2><a href="https://example.com/other">イベント開催</a></h2></article>'''
        got = kyushu_article_candidates(BeautifulSoup(html, "html.parser"), KYUSHU_SOURCES[0])
        self.assertEqual(got, [("https://www.michinoeki-kurume.com/shinmaifair/",
                                "【イベント情報】新米フェアのお知らせ")])

    def test_kyushu_2025_kadena_past_notice(self):
        self.assertEqual(kyushu_event_period("10月26日（日）イベント",date(2025, 10,21)),
                         ("2025-10-26","2025-10-26"))

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

    def test_hokuriku_same_article_on_different_calendar_days(self):
        base = {"roadName":"氷見", "prefecture":"富山県",
                "startDate":"2026-10-03", "endDate":"2026-10-12",
                "status":"scheduled"}
        a = dict(base, title="ひみ番屋街創業14周年感謝祭",
                 url="https://www.hokuriku-michinoeki.jp/contents/event/?dc=2026-10-10&article=000960")
        b = dict(base, title="ひみ番屋街創業14周年感謝祭 長い記事紹介文",
                 url="https://www.hokuriku-michinoeki.jp/contents/event/?dc=2026-10-03&article=000960")
        collected = coalesce_hokuriku_records([a, b])
        self.assertEqual(len(collected), 1)
        self.assertEqual(collected[0]["title"], a["title"])
        self.assertEqual(collected[0]["url"],
                         "https://www.hokuriku-michinoeki.jp/contents/event/?dc=2026-10-03&article=000960")
        records, audit = reconcile([a, b], [b, a], date(2026,10,10))
        self.assertEqual(len(records), 1)
        self.assertEqual(audit["collapsedHokurikuDuplicates"], {"previous":1,"collected":1})
        self.assertEqual(audit["notReconfirmed"], [])

    def test_hokuriku_different_article_same_day_kept(self):
        base = {"roadName":"氷見", "prefecture":"富山県",
                "startDate":"2026-10-25", "endDate":"2026-10-25",
                "title":"秋の催し", "status":"scheduled"}
        a = dict(base, url="https://www.hokuriku-michinoeki.jp/contents/event/?dc=2026-10-25&article=000961")
        b = dict(base, url="https://www.hokuriku-michinoeki.jp/contents/event/?dc=2026-10-25&article=000962")
        records, audit = reconcile([], [a,b], date(2026,10,10))
        self.assertEqual(len(records), 2)
        self.assertEqual(audit["collapsedHokurikuDuplicates"]["collected"], 0)

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

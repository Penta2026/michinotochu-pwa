"""Offline Phase 2 tests: new-event discovery from official HTML station rules."""
import unittest
from datetime import date
from bs4 import BeautifulSoup

from station_discovery_engine import (
    _article_record, _links, _period, _official_url, _validate_sources,
    collect_configured_station_events,
)

TODAY = date(2026, 10, 10)
TOKYO = {
    "id": "tokyo", "enabled": True, "prefecture": "東京都",
    "roadName": "八王子滝山",
    "listingUrl": "https://www.michinoeki-hachioji.net/",
    "allowedHosts": ["www.michinoeki-hachioji.net"],
    "articlePathPattern": r"^/news/[0-9]+/?$",
    "listingLinkSelector": "a[href]",
    "articleSelector": "article",
    "titleSelectors": ["article h1"],
    "requiredVenueTokens": ["道の駅八王子滝山"],
    "maxArticles": 8,
}
NARA = {
    **TOKYO, "id": "nara", "prefecture": "奈良県",
    "roadName": "クロスウェイなかまち",
    "listingUrl": "https://michi-no-eki-crosswaynakamachi.pref.nara.jp/newslist",
    "allowedHosts": ["michi-no-eki-crosswaynakamachi.pref.nara.jp"],
    "articlePathPattern": r"^/events/[0-9]{8}/?$",
    "requiredVenueTokens": ["クロスウェイなかまち"],
}
URL = "https://www.michinoeki-hachioji.net/news/1001"
LISTING = '<ul><li><a href="/news/1001">10/24(土) 秋の物産展を開催！</a></li></ul>'
ARTICLE = """<article><h1>10/24(土) 秋の物産展を開催！</h1>
    <time datetime="2026-10-01">2026年10月1日</time>
    <p>開催日時：10月24日（土）10:00～16:00</p>
    <p>開催場所：道の駅八王子滝山 交流ホール</p></article>"""

def soup(html):
    return BeautifulSoup(html, "html.parser")

class ConfiguredDiscoveryTests(unittest.TestCase):
    def test_registry_must_have_official_https_host(self):
        _validate_sources([TOKYO,NARA])
        self.assertTrue(_official_url(URL, TOKYO, article=True))
        for bad in ("http://www.michinoeki-hachioji.net/news/1001",
                    "https://evil.example/news/1001",
                    "https://www.michinoeki-hachioji.net.evil.example/news/1001",
                    "https://www.michinoeki-hachioji.net:443/news/1001",
                    "https://www.michinoeki-hachioji.net/news/abc"):
            self.assertFalse(_official_url(bad, TOKYO, article=True))

    def test_duplicate_rule_id_or_unsafe_source_rejected(self):
        with self.assertRaises(ValueError):
            _validate_sources([TOKYO,TOKYO])
        with self.assertRaises(ValueError):
            _validate_sources([{**TOKYO,"listingUrl":"http://evil.example/"}])

    def test_official_link_discovery_and_external_link_block(self):
        listing = soup(LISTING + '<a href="https://evil.example/news/1002">祭り</a>'
                       + '<a href="/news/1001">duplicate article</a>')
        self.assertEqual(list(_links(listing,TOKYO)),[URL])

    def test_article_date_and_station_venue_must_match(self):
        rec,status = _article_record(TOKYO,soup(ARTICLE),"秋の物産展",TODAY,URL)
        self.assertEqual(status,"accepted")
        self.assertEqual((rec["startDate"],rec["endDate"]),
                         ("2026-10-24","2026-10-24"))
        self.assertEqual(rec["prefecture"],"東京都")
        self.assertEqual(rec["publishedAt"],"2026-10-01")

    def test_full_date_era_conversion(self):
        self.assertEqual(_period("令和8年10月24日(土)",None),
                         ("2026-10-24","2026-10-24"))
        self.assertIsNone(_period("令和7年10月24日(土)",None))

    def test_event_with_no_grounded_year_is_rejected(self):
        article = soup("""<article><h1>10/24(土) 秋の物産展を開催</h1>
            <p>開催日時：10月24日(土)</p>
            <p>会場：道の駅八王子滝山</p></article>""")
        rec,reason=_article_record(TOKYO,article,"10/24 物産展",TODAY,URL)
        self.assertEqual((rec,reason),(None,"undated"))

    def test_monthly_image_calendar_is_rejected(self):
        article=soup("""<article><h1>10月イベントカレンダー</h1>
            <img src="oct.jpg"/><p>道の駅八王子滝山</p></article>""")
        rec,reason=_article_record(TOKYO,article,"10月イベントカレンダー",TODAY,URL)
        self.assertIsNone(rec)
        self.assertEqual(reason,"not_event")

    def test_offsite_location_is_rejected(self):
        body=ARTICLE.replace("道の駅八王子滝山 交流ホール","市役所大ホール") + ""
        body=body.replace("</article>","<p>主催：道の駅八王子滝山</p></article>")
        rec,reason=_article_record(TOKYO,soup(body),"秋の物産展",TODAY,URL)
        self.assertEqual((rec,reason),(None,"offsite"))

    def test_station_venue_absent_rejected(self):
        body=ARTICLE.replace("道の駅八王子滝山 交流ホール","市役所大ホール")
        rec,reason=_article_record(TOKYO,soup(body),"物産展",TODAY,URL)
        self.assertEqual((rec,reason),(None,"venue_missing"))

    def test_posting_date_only_is_not_event_date(self):
        body=ARTICLE.replace("開催日時：10月24日（土）10:00～16:00",
                            "イベント内容は後日お知らせします")
        rec,reason=_article_record(TOKYO,soup(body),"物産展",TODAY,URL)
        # The title contains 10/24, and this is positive event-date evidence.
        self.assertEqual(reason,"accepted")
        undated = body.replace("10/24(土) 秋の物産展", "秋の物産展")
        rec,reason=_article_record(TOKYO,soup(undated),"物産展",TODAY,URL)
        self.assertEqual((rec,reason),(None,"undated"))

    def test_future_publication_timestamp_cannot_ground_short_date(self):
        body=ARTICLE.replace("2026-10-01","2026-11-01").replace("2026年10月1日","2026年11月1日")
        # Title "10/24" has no explicit year, so future post stamp is not trusted.
        rec,reason=_article_record(TOKYO,soup(body),"物産展",TODAY,URL)
        self.assertEqual((rec,reason),(None,"undated"))

    def test_nara_2025_notice_does_not_reyear(self):
        url="https://michi-no-eki-crosswaynakamachi.pref.nara.jp/events/20251011"
        body=soup("""<article><h1>10月11日(土) 天理市フェア開催</h1>
            <time datetime="2025-09-30">2025年9月30日</time>
            <p>開催期間：2025年10月11日(土)～19日(日)</p>
            <p>会場：クロスウェイなかまち</p></article>""")
        rec,reason=_article_record(NARA,body,"天理市フェア",TODAY,url)
        self.assertEqual((rec,reason),(None,"past"))

    def test_new_event_discovered_without_changing_existing_records(self):
        fetched={TOKYO["listingUrl"]:LISTING,URL:ARTICLE}
        new,audit=collect_configured_station_events(
            TODAY,[],[TOKYO],fetch=lambda u:soup(fetched[u]),report_path=None)
        self.assertEqual(len(new),1)
        self.assertEqual(new[0]["url"],URL)
        self.assertEqual(audit["newEvents"],1)
        self.assertEqual(audit["sources"][0]["accepted"],1)

    def test_known_article_url_skips_duplicate_even_if_title_varies(self):
        fetched={TOKYO["listingUrl"]:LISTING}
        previous=[{"url":URL,"title":"旧タイトル"}]
        new,audit=collect_configured_station_events(
            TODAY,previous,[TOKYO],fetch=lambda u:soup(fetched[u]),report_path=None)
        self.assertEqual(new,[])
        self.assertEqual(audit["sources"][0]["knownSkipped"],1)

    def test_per_station_error_is_reported_without_losing_other_stations(self):
        failed={**TOKYO,"id":"fail","listingUrl":"https://www.michinoeki-hachioji.net/fail"}
        def get(url):
            if url.endswith("/fail"):
                raise __import__("requests").Timeout("offline")
            return soup({TOKYO["listingUrl"]:LISTING,URL:ARTICLE}[url])
        new,audit=collect_configured_station_events(
            TODAY,[],[failed,TOKYO],fetch=get,report_path=None)
        self.assertEqual(len(new),1)
        self.assertIn("Timeout",audit["sources"][0]["listingError"])
        self.assertEqual(audit["sources"][1]["accepted"],1)

    def test_nara_event_and_official_station(self):
        url="https://michi-no-eki-crosswaynakamachi.pref.nara.jp/events/20261031"
        text="""<main><article><h1>10/31(土) まほろばの宴を開催！</h1>
          <time datetime="2026-10-06">10月6日</time>
          <p>道の駅「クロスウェイなかまち」で
          10月31日（土）開催です。</p></article></main>"""
        rec,why=_article_record(NARA,soup(text),"10/31 まほろばの宴",TODAY,url)
        self.assertEqual(why,"accepted")
        self.assertEqual(rec["startDate"],"2026-10-31")


    def test_expanded_registry_config_has_three_new_prefectures(self):
        import json
        from station_discovery_engine import RULES
        rules=json.loads(RULES.read_text(encoding="utf-8"))["sources"]
        self.assertGreaterEqual(len(rules),7)
        self.assertTrue({"福井県","大阪府","和歌山県"}.issubset(
            set(rule["prefecture"] for rule in rules)))
        _validate_sources(rules)

    def test_fukui_official_root_level_article_slug(self):
        src={**TOKYO,"id":"fukui","listingUrl":"https://hamabiyori.com/events/",
             "allowedHosts":["hamabiyori.com"],
             "articlePathPattern":r"^/(?!events/?$)[^/]+/?$"}
        self.assertTrue(_official_url(
            "https://hamabiyori.com/%F0%9F%8E%AAexample/",src,article=True))
        self.assertFalse(_official_url(src["listingUrl"],src,article=True))

    def test_osaka_explicit_on_site_venue_and_unlabelled_yearly_date(self):
        spec={**TOKYO,"id":"osaka","roadName":"いずみ山愛の里",
            "prefecture":"大阪府","requiredVenueTokens":["南部リージョンセンター"],
            "allowExplicitDatedParagraph":True,"requireVenueLabel":True}
        html="""<article><h1>いずみの山の小さなマルシェ10月</h1>
           <p>月イチマルシェを開催しています。</p>
           <p>2026年10月18日（日）10:00～16:00頃</p>
           <p>会場：南部リージョンセンター1階ロビー</p>
           </article>"""
        rec,why=_article_record(spec,soup(html),"マルシェ10月",TODAY,URL)
        self.assertEqual(why,"accepted")
        self.assertEqual(rec["startDate"],"2026-10-18")
        self.assertEqual(rec["prefecture"],"大阪府")

    def test_osaka_related_publicity_without_venue_label_is_not_station_event(self):
        spec={**TOKYO,"requiredVenueTokens":["南部リージョンセンター"],
              "requireVenueLabel":True,"allowExplicitDatedParagraph":True}
        html="""<article><h1>秋のマルシェ</h1>
           <p>主催：南部リージョンセンター</p>
           <p>2026年10月18日（日）開催</p></article>"""
        self.assertEqual(_article_record(spec,soup(html),"秋のマルシェ",TODAY,URL),
                         (None,"venue_missing"))

    def test_osaka_shared_site_onsite_lobby_is_strictly_verified(self):
        spec={**TOKYO,"id":"osaka_shared","roadName":"いずみ山愛の里",
              "prefecture":"大阪府",
              "requiredVenueTokens":["南部リージョンセンター"],
              "allowExplicitDatedParagraph":True,
              "requireVenueLabel":True,
              "venueProofPattern":r"南部リージョンセンタ[ー-].{0,35}(?:1階|ロビ[ー-])"}
        article=soup("""<article><h1>いずみの山の小さなマルシェ10月</h1>
           <time datetime="2026-10-02">2026年10月2日</time>
           <p>2026年10月18日（日）10:00～16:00</p>
           <p>和泉市南部リージョンセンタ－　１階ロビ－</p></article>""")
        result,why=_article_record(spec,article,"マルシェ",TODAY,URL)
        self.assertEqual(why,"accepted")
        self.assertEqual(result["startDate"],"2026-10-18")

    def test_osaka_unlabelled_publication_timestamp_not_event_date(self):
        spec={**TOKYO,"requiredVenueTokens":["南部リージョンセンター"],
              "allowExplicitDatedParagraph":True,"requireVenueLabel":True}
        html="""<article><h1>秋のマルシェ</h1>
          <time datetime="2026-10-05">2026年10月5日</time>
          <p>2026年10月5日 10:00</p>
          <p>会場：南部リージョンセンター1階ロビー</p></article>"""
        rec,why=_article_record(spec,soup(html),"秋のマルシェ",TODAY,URL)
        self.assertEqual((rec,why),(None,"undated"))

    def test_osaka_unlabelled_year_without_time_requires_event_context(self):
        spec={**TOKYO,"requiredVenueTokens":["南部リージョンセンター"],
              "allowExplicitDatedParagraph":True,"requireVenueLabel":True}
        html="""<article><h1>秋のマルシェ</h1>
          <p>2026年10月18日（日）</p>
          <p>会場：南部リージョンセンター1階ロビー</p></article>"""
        rec,why=_article_record(spec,soup(html),"秋のマルシェ",TODAY,URL)
        self.assertEqual((rec,why),(None,"undated"))

    def test_wakayama_multi_notice_extracts_two_independently_dated_events(self):
        from station_discovery_engine import _section_records
        spec={**TOKYO,"id":"sakuas","prefecture":"和歌山県",
              "roadName":"海南サクアス",
              "requiredVenueTokens":["海南サクアス"],
              "approvedVenueTokens":["催事スペース","エントランス広場"]}
        html="""<main><h1>10月イベント情報</h1>
           <time datetime="2026-09-28">2026.9.28</time>
           <p>道の駅『海南サクアス』では催し物をご用意しました。</p>
           <p>〖北海道うまいっしょ市〗</p>
           <p>🗓10月17日(土)～10月18日(日)</p>
           <p>📍催事スペース</p>
           <p>〖音楽LIVE♬〗</p>
           <p>🗓10月24日(土) 11:00～</p>
           <p>📍エントランス広場</p>
           </main>"""
        actual,why=_section_records(spec,soup(html),TODAY,
                                    "https://sakuas.com/event/9999/")
        self.assertEqual(why,"accepted")
        self.assertEqual(len(actual),2)
        self.assertEqual([x["startDate"] for x in actual],
                         ["2026-10-17","2026-10-24"])
        self.assertEqual(actual[0]["endDate"],"2026-10-18")
        self.assertNotEqual(actual[0]["title"],actual[1]["title"])

    def test_wakayama_article_heading_supplies_publication_year_even_with_narrow_selector(self):
        from station_discovery_engine import _section_records
        # Configured "article h1" cannot match <main><h1>, but the parser
        # should use the actual heading next to the official <time> value.
        spec={**TOKYO,"id":"sakuas","roadName":"海南サクアス",
              "requiredVenueTokens":["海南サクアス"],
              "approvedVenueTokens":["催事スペース"]}
        html="""<main><h1>10月イベント情報</h1>
           <time datetime="2026-09-28"></time>
           <p>道の駅海南サクアスの催し</p>
           <p>〖秋のマルシェ〗</p>
           <p>🗓10月24日(土)</p><p>📍催事スペース</p>
           </main>"""
        events,why=_section_records(spec,soup(html),TODAY,
                                    "https://sakuas.com/event/1234/")
        self.assertEqual(why,"accepted")
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]["startDate"],"2026-10-24")
        self.assertEqual(events[0]["publishedAt"],"2026-09-28")

    def test_wakayama_multi_requires_onsite_venue_and_grounded_year(self):
        from station_discovery_engine import _section_records
        spec={**TOKYO,"id":"sakuas","roadName":"海南サクアス",
              "requiredVenueTokens":["海南サクアス"],
              "approvedVenueTokens":["催事スペース"]}
        html="""<main><h1>10月イベント情報</h1>
          <p>道の駅海南サクアスからのお知らせ</p>
          <p>〖マルシェ〗</p><p>🗓10月24日(土)</p><p>📍市役所広場</p>
          <p>〖秋のフェア〗</p><p>🗓10月31日(土)</p><p>📍催事スペース</p>
          </main>"""
        result,why=_section_records(spec,soup(html),TODAY,
                                    "https://sakuas.com/event/9999/")
        self.assertEqual(result,[])
        self.assertEqual(why,"no_individually_dated_sections")

    def test_wakayama_multi_does_not_block_same_article_later_events(self):
        spec={**TOKYO,"id":"sakuas","roadName":"海南サクアス",
              "prefecture":"和歌山県",
              "listingUrl":"https://sakuas.com/event/",
              "allowedHosts":["sakuas.com"],
              "articlePathPattern":r"^/event/[0-9]+/?$",
              "articleMode":"dated_sections","maxArticles":3,
              "requiredVenueTokens":["海南サクアス"],
              "approvedVenueTokens":["催事スペース"]}
        url="https://sakuas.com/event/1234/"
        html="""<main><h1>10月イベント情報</h1>
           <time datetime="2026-09-28"></time>
           <p>道の駅 海南サクアスの催しです</p>
           <p>〖北海道うまいっしょ市〗</p>
           <p>🗓10月17日(土)</p><p>📍催事スペース</p>
           <p>〖秋の音楽LIVE〗</p>
           <p>🗓10月24日(土)</p><p>📍催事スペース</p></main>"""
        prior=[{"url":url,"roadName":"海南サクアス","prefecture":"和歌山県",
                "title":"北海道うまいっしょ市","startDate":"2026-10-17",
                "endDate":"2026-10-17"}]
        fetch=lambda u:soup({spec["listingUrl"]:
            '<a href="/event/1234/">10月イベント情報</a>',url:html}[u])
        result,audit=collect_configured_station_events(
            TODAY,prior,[spec],fetch=fetch,report_path=None)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["title"],"秋の音楽LIVE")
        self.assertEqual(audit["sources"][0]["accepted"],1)

    def test_wakayama_multi_never_registers_image_only_calendar(self):
        from station_discovery_engine import _section_records
        spec={**TOKYO,"id":"sakuas","roadName":"海南サクアス",
              "requiredVenueTokens":["海南サクアス"],
              "approvedVenueTokens":["催事スペース"]}
        html="""<main><h1>10月イベントカレンダー</h1>
            <p>道の駅海南サクアスのお知らせ</p>
            <img src="october.png"/></main>"""
        records,why=_section_records(spec,soup(html),TODAY,
                                     "https://sakuas.com/event/100/")
        self.assertEqual(records,[])


    def test_gap_prefecture_registry_has_all_six(self):
        import json
        from station_discovery_engine import RULES
        config=json.loads(RULES.read_text(encoding="utf-8"))
        specs=config["sources"]
        self.assertGreaterEqual(len(specs),13)
        self.assertTrue({"岩手県","山形県","福島県","静岡県","山口県","愛媛県"}.issubset(
            {x["prefecture"] for x in specs}))
        _validate_sources(specs)

    def test_official_yamagata_program_explicit_2026_dates(self):
        from station_discovery_engine import _official_program_records
        spec={**TOKYO,"id":"yamagata","prefecture":"山形県",
              "roadName":"たかはた","requiredVenueTokens":["道の駅たかはた"],
              "articleSelector":"body","articleMode":"official_station_program",
              "sectionEventNames":["秋の収穫祭"]}
        html="""<body><div>道の駅たかはた</div>
          <div>令和8年度・2026年度開催イベント</div>
          <p>秋の収穫祭</p>
          <p>2026年10月11日(日)・12日(月祝)</p>
          <p>新米や地元農産物の販売</p></body>"""
        events,why=_official_program_records(spec,soup(html),TODAY,
                          "https://www.rstakahata.com/rst/event.html")
        self.assertEqual(why,"accepted")
        self.assertEqual(len(events),1)
        self.assertEqual((events[0]["startDate"],events[0]["endDate"]),
                         ("2026-10-11","2026-10-12"))
        self.assertEqual(events[0]["prefecture"],"山形県")

    def test_yamagata_2025_program_does_not_become_2026(self):
        from station_discovery_engine import _official_program_records
        spec={**TOKYO,"id":"yamagata","prefecture":"山形県",
              "roadName":"たかはた","requiredVenueTokens":["道の駅たかはた"],
              "articleSelector":"body","sectionEventNames":["秋の収穫祭"]}
        html="""<body><h1>道の駅たかはた</h1>
          <p>令和8年度・2026年度イベント</p>
          <p>秋の収穫祭</p><p>2025年10月11日(土)・12日(日)</p>
          </body>"""
        events,why=_official_program_records(spec,soup(html),TODAY,
                          "https://www.rstakahata.com/rst/event.html")
        self.assertEqual(events,[])
        self.assertEqual(why,"no_grounded_program_event")

    def test_yamagata_program_self_listing_requires_no_article_link(self):
        from station_discovery_engine import _links
        spec={**TOKYO,"listingUrl":"https://www.rstakahata.com/rst/event.html",
              "articlePathPattern":r"^/rst/event\.html$",
              "allowedHosts":["www.rstakahata.com"],
              "articleMode":"official_station_program"}
        self.assertEqual(_links(soup("<body><p>道の駅たかはた</p></body>"),spec),
                         {spec["listingUrl"]:"公式開催案内"})

    def test_fukushima_short_date_grounded_by_official_listing_posted(self):
        from station_discovery_engine import _article_record
        spec={**TOKYO,"id":"fukushima","roadName":"ふくしま",
              "prefecture":"福島県","requiredVenueTokens":["多目的広場"],
              "allowedEventWords":["フェスタ"],"useListingPublicationDate":True}
        html="""<main><h3>〖10/10(土)・11日(日)ガーデンプレイスフェスタ〗</h3>
            <p>〖日時〗10月10日(土)・11日(日)10:00～16:00</p>
            <p>〖場所〗多目的広場</p></main>"""
        listing="EVENT 2026.10.08 〖10/10(土)・11日(日)ガーデンプレイスフェスタ〗"
        rec,why=_article_record(spec,soup(html),listing,TODAY,
                                "https://m-fukushima.com/info/700")
        self.assertEqual(why,"accepted")
        self.assertEqual((rec["startDate"],rec["endDate"]),
                         ("2026-10-10","2026-10-11"))
        self.assertEqual(rec["prefecture"],"福島県")

    def test_fukushima_does_not_guess_year_if_listing_undated(self):
        from station_discovery_engine import _article_record
        spec={**TOKYO,"requiredVenueTokens":["多目的広場"],
              "allowedEventWords":["フェスタ"],"useListingPublicationDate":True}
        html="""<main><h3>10/10(土) ガーデンプレイスフェスタ</h3>
                 <p>〖日時〗10月10日(土)</p><p>〖場所〗多目的広場</p></main>"""
        rec,why=_article_record(spec,soup(html),"イベント",TODAY,URL)
        self.assertEqual((rec,why),(None,"undated"))

    def test_fukushima_h3_detail_takes_priority_over_listing_post_date(self):
        from station_discovery_engine import _headline
        spec={**TOKYO,"requiredVenueTokens":["多目的広場"],
              "allowedEventWords":["フェスタ"],"useListingPublicationDate":True}
        listing="EVENT 2026.10.08 〖10/10(土)・11日(日)ガーデンプレイスフェスタ〗"
        detail=soup("""<main><h3>〖10/10(土)・11日(日)ガーデンプレイスフェスタ〗</h3>
                   <p>〖日時〗10月10日(土)・11日(日)</p>
                   <p>〖場所〗多目的広場</p></main>""")
        self.assertEqual(_headline(detail,spec,listing),
                         "〖10/10(土)・11日(日)ガーデンプレイスフェスタ〗")

    def test_fukushima_listing_posting_date_alone_never_becomes_event(self):
        from station_discovery_engine import _article_record, _headline
        spec={**TOKYO,"requiredVenueTokens":["多目的広場"],
              "allowedEventWords":["フェスタ"],"useListingPublicationDate":True}
        listing="EVENT 2026.10.08 ガーデンプレイスフェスタ"
        detail=soup("""<main><p>日時は後日発表いたします</p>
                   <p>〖場所〗多目的広場</p></main>""")
        self.assertEqual(_headline(detail,spec,listing),"ガーデンプレイスフェスタ")
        rec,why=_article_record(spec,detail,listing,TODAY,URL)
        self.assertEqual((rec,why),(None,"undated"))

    def test_shizuoka_monthly_program_extracts_separately(self):
        from station_discovery_engine import _monthly_calendar_records
        spec={**TOKYO,"id":"shizuoka","prefecture":"静岡県",
              "roadName":"伊豆ゲートウェイ函南",
              "articleSelector":"article",
              "monthlyEventWords":["ピスタチオ","食市","干し柿","フェス"]}
        html="""<article><h1>2026年11月 道の駅イベントのご案内</h1>
           <time datetime="2026-10-03">2026.10.03</time>
           <h3>翠のピスタチオ</h3><p>11月8日(日)10:00～15:00</p>
           <p>道の駅で静岡茶も楽しめます</p>
           <h3>ゲートウェイ食市 干し柿づくり</h3>
           <p>11月21日(土)10:00～15:00</p>
           <p>道の駅でのワークショップです</p></article>"""
        rec,why=_monthly_calendar_records(spec,soup(html),TODAY,
                   "https://www.izugateway.com/event/6779/")
        self.assertEqual(why,"accepted")
        self.assertEqual(len(rec),2)
        self.assertEqual([x["startDate"] for x in rec],
                         ["2026-11-08","2026-11-21"])
        self.assertEqual([x["prefecture"] for x in rec],["静岡県","静岡県"])

    def test_shizuoka_monthly_rejects_wrong_weekday(self):
        from station_discovery_engine import _monthly_calendar_records
        spec={**TOKYO,"articleSelector":"article","monthlyEventWords":["フェス"]}
        html="""<article><h1>2026年11月 道の駅イベントのご案内</h1>
          <h3>芋フェス</h3><p>11月22日(土)10:00</p></article>"""
        rec,why=_monthly_calendar_records(spec,soup(html),TODAY,URL)
        self.assertEqual(rec,[])
        self.assertEqual(why,"no_individually_dated_monthly_events")

    def test_shizuoka_monthly_never_infers_year_from_current_date(self):
        from station_discovery_engine import _monthly_calendar_records
        spec={**TOKYO,"articleSelector":"article","monthlyEventWords":["フェス"]}
        html="""<article><h1>11月のイベントカレンダー</h1>
          <h3>芋フェス</h3><p>11月21日(土)10:00</p></article>"""
        rec,why=_monthly_calendar_records(spec,soup(html),TODAY,URL)
        self.assertEqual(rec,[])
        self.assertEqual(why,"no_grounded_program_year")

    def test_shizuoka_monthly_refuses_offsite_event(self):
        from station_discovery_engine import _monthly_calendar_records
        spec={**TOKYO,"articleSelector":"article","monthlyEventWords":["フェス"]}
        html="""<article><h1>2026年11月 道の駅イベントのご案内</h1>
          <h3>川の駅フェス</h3><p>11月21日(土)10:00</p>
          <p>川の駅で開催予定です</p></article>"""
        rec,why=_monthly_calendar_records(spec,soup(html),TODAY,URL)
        self.assertEqual(rec,[])
        self.assertEqual(why,"no_individually_dated_monthly_events")

    def test_official_listing_posted_never_uses_future_timestamp(self):
        from station_discovery_engine import _listing_posted
        self.assertEqual(_listing_posted("EVENT 2026.10.08 秋のフェスタ",TODAY),
                         date(2026,10,8))
        self.assertIsNone(_listing_posted("EVENT 2026.10.20 秋のフェスタ",TODAY))
        self.assertIsNone(_listing_posted("EVENT 10.08 秋のフェスタ",TODAY))

    def test_eleven_zero_event_prefectures_have_new_official_choices(self):
        import json
        from station_discovery_engine import RULES
        sources=json.loads(RULES.read_text(encoding="utf-8"))["sources"]
        self.assertEqual(len(sources),21)
        expected={"山口県","福井県","大阪府","熊本県","宮崎県"}
        self.assertTrue(expected.issubset({r["prefecture"] for r in sources}))
        self.assertTrue(all(r["enabled"] for r in sources))
        _validate_sources(sources)

    def test_osaka_station_official_dated_table_extracts_marché(self):
        from station_discovery_engine import _dated_station_table_records
        spec={**TOKYO,"id":"kuromaro","prefecture":"大阪府",
              "roadName":"奥河内くろまろの郷",
              "listingUrl":"https://kuromaro.com/event/list/page/4/",
              "allowedHosts":["kuromaro.com"],
              "articlePathPattern":r"^/event/.*$",
              "requireCategoryTokens":["バザール広場イベント"],
              "allowedEventWords":["くろまろマルシェ"],
              "articleMode":"dated_station_table"}
        html="""<table><tr><th>実施日</th><th>カテゴリ</th><th>イベント名</th></tr>
          <tr><td>2026年10月24日～10月25日</td>
            <td>バザール広場イベント</td>
            <td><a href="/event/124/">（全面）第25回 奥河内くろまろマルシェ 1024-1025</a></td></tr>
          <tr><td>2026年10月25日～10月25日</td>
            <td>周辺施設</td><td>奥河内くろまろマルシェ</td></tr>
          </table>"""
        result,why=_dated_station_table_records(
            spec,soup(html),TODAY,spec["listingUrl"])
        self.assertEqual(why,"accepted")
        self.assertEqual(len(result),1)
        self.assertEqual((result[0]["startDate"],result[0]["endDate"]),
                         ("2026-10-24","2026-10-25"))
        self.assertEqual(result[0]["roadName"],"奥河内くろまろの郷")

    def test_osaka_event_list_never_guesses_year_from_numeric_title(self):
        from station_discovery_engine import _dated_station_table_records
        spec={**TOKYO,"id":"kuromaro","requiredVenueTokens":["奥河内"],
              "allowedHosts":["kuromaro.com"],
              "requireCategoryTokens":["バザール広場イベント"],
              "allowedEventWords":["マルシェ"]}
        html="""<table><tr><td>10月24日～25日</td>
        <td>バザール広場イベント</td><td>マルシェ 1024-1025</td></tr></table>"""
        result,why=_dated_station_table_records(
            spec,soup(html),TODAY,"https://kuromaro.com/event/list/")
        self.assertEqual(result,[])
        self.assertEqual(why,"no_official_dated_station_rows")

    def test_yamaguchi_abucho_reiwa_title_event_and_official_venue(self):
        from station_discovery_engine import _article_record
        spec={**TOKYO,"roadName":"阿武町","prefecture":"山口県",
              "articleSelector":"article","titleSelectors":["h1"],
              "allowedEventWords":["森里海の市"],
              "requiredVenueTokens":["道の駅阿武町"],"requireVenueLabel":True}
        html="""<article>
          <h1>令和8年10月11日(日)第48回森里海の市を開催します。</h1>
          <h2>開催日</h2><p>開催日：令和8年10月11日(日)</p>
          <p>開催場所：道の駅阿武町</p></article>"""
        rec,why=_article_record(spec,soup(html),"第48回森里海の市",TODAY,
                                "https://www.abucreation.com/topics/official/")
        self.assertEqual(why,"accepted")
        self.assertEqual(rec["startDate"],"2026-10-11")

    def test_yamaguchi_not_only_a_recruitment_notice(self):
        from station_discovery_engine import _article_record
        spec={**TOKYO,"roadName":"阿武町",
              "articleSelector":"article","titleSelectors":["h1"],
              "allowedEventWords":["森里海の市"],
              "requiredVenueTokens":["道の駅阿武町"],"requireVenueLabel":True}
        html="""<article><h1>森里海の市 出店者募集</h1>
           <p>開催日：令和8年10月11日(日)</p>
           <p>開催場所：道の駅阿武町</p></article>"""
        rec,why=_article_record(spec,soup(html),"募集",TODAY,URL)
        self.assertIsNone(rec)

    def test_kumamoto_tourism_detail_stated_station_venue(self):
        from station_discovery_engine import _article_record
        spec={**TOKYO,"articleSelector":"article",
              "titleSelectors":["h1"],"dateSelectors":"p,tr,td",
              "requiredVenueTokens":["道の駅あそ望の郷くぎの"],
              "allowedEventWords":["青空レストラン"],"requireVenueLabel":True,
              "roadName":"あそ望の郷くぎの","prefecture":"熊本県"}
        html="""<article><h1>第11回 南阿蘇の青空レストラン</h1>
          <table><tr><th>日時</th><td>2026年10月12日（月）10:00～16:00</td></tr>
          <tr><th>会場</th><td>道の駅あそ望の郷くぎの 芝生広場</td></tr></table></article>"""
        rec,why=_article_record(spec,soup(html),"青空レストラン",TODAY,URL)
        self.assertEqual(why,"accepted")
        self.assertEqual(rec["startDate"],"2026-10-12")

    def test_kumamoto_tourism_other_event_venue_rejected(self):
        from station_discovery_engine import _article_record
        spec={**TOKYO,"articleSelector":"article",
              "titleSelectors":["h1"],"dateSelectors":"p,tr,td",
              "requiredVenueTokens":["道の駅あそ望の郷くぎの"],
              "allowedEventWords":["青空レストラン"],"requireVenueLabel":True}
        html="""<article><h1>青空レストラン</h1>
          <p>協力：道の駅あそ望の郷くぎの</p>
          <table><tr><th>日時</th><td>2026年10月12日（月）</td></tr>
          <tr><th>会場</th><td>別会場 熊本市ホール</td></tr></table></article>"""
        rec,why=_article_record(spec,soup(html),"青空レストラン",TODAY,URL)
        self.assertEqual((rec,why),(None,"offsite"))

    def test_miyazaki_r8_11month_event_year_from_paragraph(self):
        from station_discovery_engine import _article_record
        spec={**TOKYO,"articleSelector":"article",
              "titleSelectors":["h1"],"allowedEventWords":["蕎麦打ち"],
              "requiredVenueTokens":["NiQLL"],"allowExplicitDatedParagraph":True}
        html="""<article><h1>〖NiQLLキッチン〗11月 秋の蕎麦打ち体験</h1>
          <p>R8 11月10日(火)NiQLLキッチン「秋の蕎麦打ち体験」開催！</p>
          </article>"""
        rec,why=_article_record(spec,soup(html),"蕎麦打ち",TODAY,URL)
        self.assertEqual(why,"accepted")
        self.assertEqual(rec["startDate"],"2026-11-10")

    def test_miyazaki_undated_class_announcement_not_event_period(self):
        from station_discovery_engine import _article_record
        spec={**TOKYO,"articleSelector":"article",
              "titleSelectors":["h1"],"allowedEventWords":["蕎麦打ち"],
              "requiredVenueTokens":["NiQLL"],"allowExplicitDatedParagraph":True}
        html="""<article><h1>NiQLL 秋の蕎麦打ち体験</h1>
          <p>日程詳細は後日ご案内いたします</p></article>"""
        rec,why=_article_record(spec,soup(html),"蕎麦打ち",TODAY,URL)
        self.assertEqual((rec,why),(None,"undated"))

    def test_ehime_city_official_notice_with_station_venue(self):
        from station_discovery_engine import _article_record
        spec={**TOKYO,"prefecture":"愛媛県","roadName":"八幡浜みなっと",
              "allowedEventWords":["産業まつり"],"requiredVenueTokens":["八幡浜みなっと"],
              "requireVenueLabel":True,"articleSelector":"article"}
        html="""<article>
           <h1>第１３回やわたはま産業まつりについて</h1>
           <p>開催日時：令和８年１１月２２日（日）午前１０時～午後４時</p>
           <p>開催場所：道の駅・みなとオアシス「八幡浜みなっと」</p>
           </article>"""
        rec,why=_article_record(spec,soup(html),"産業まつり",TODAY,
                                "https://www.city.yawatahama.ehime.jp/doc/123456/")
        self.assertEqual(why,"accepted")
        self.assertEqual((rec["startDate"],rec["endDate"]),
                         ("2026-11-22","2026-11-22"))

    def test_ehime_city_festival_at_other_venue_rejected(self):
        from station_discovery_engine import _article_record
        spec={**TOKYO,"roadName":"八幡浜みなっと",
              "requiredVenueTokens":["八幡浜みなっと"],
              "allowedEventWords":["産業まつり"],"requireVenueLabel":True}
        html="""<article><h1>産業まつり</h1>
            <p>主催：八幡浜みなっと運営委員会</p>
            <p>開催日時：2026年11月22日（日）</p>
            <p>開催場所：八幡浜市役所</p></article>"""
        rec,why=_article_record(spec,soup(html),"産業まつり",TODAY,URL)
        self.assertEqual((rec,why),(None,"offsite"))

    def test_wakayama_station_article_without_station_name_but_with_venue(self):
        from station_discovery_engine import _section_records
        spec={**TOKYO,"roadName":"海南サクアス",
              "requiredVenueTokens":["海南サクアス"],
              "trustArticleSectionsWithStationVenue":True,
              "approvedVenueTokens":["エントランス広場"]}
        html="""<main><h1>10月イベント情報</h1>
           <time datetime="2026-09-28"></time>
           <p>〖猿まわし〗</p>
           <p>🗓10月11日(日)～10月12日(月)</p>
           <p>📍エントランス広場</p></main>"""
        results,why=_section_records(spec,soup(html),TODAY,
                                     "https://sakuas.com/event/9999/")
        self.assertEqual(why,"accepted")
        self.assertEqual(len(results),1)
        self.assertEqual(results[0]["startDate"],"2026-10-11")

    def test_wakayama_official_article_requires_each_own_venue(self):
        from station_discovery_engine import _section_records
        spec={**TOKYO,"roadName":"海南サクアス",
              "requiredVenueTokens":["海南サクアス"],
              "trustArticleSectionsWithStationVenue":True,
              "approvedVenueTokens":["エントランス広場"]}
        html="""<main><h1>10月イベント情報</h1>
           <time datetime="2026-09-28"></time>
           <p>〖猿まわし〗</p><p>🗓10月11日(日)</p>
           <p>📍市役所ロビー</p></main>"""
        result,why=_section_records(spec,soup(html),TODAY,
                                    "https://sakuas.com/event/9999/")
        self.assertEqual(result,[])
        self.assertEqual(why,"no_individually_dated_sections")

    def test_nagasaki_himawari_official_bike_event_october(self):
        from station_discovery_engine import _article_record
        spec={**TOKYO,"roadName":"ひまわり","prefecture":"長崎県",
              "articleSelector":"article",
              "titleSelectors":["article h1"],
              "allowedEventWords":["バイクイベント"],
              "requiredVenueTokens":["道の駅ひまわり"],
              "useListingPublicationDate":True}
        article=soup("""<article><h1>バイクイベント開催 １０月１８日(日)</h1>
           <p>バイクイベント開催 １０月１８日(日) 10:00～15:00</p>
           <p>場所 道の駅ひまわり</p>
           <p>主催 K.R.factory＋M</p></article>""")
        listing="2026.10.07 バイクイベント開催 １０月１８日(日)"
        rec,why=_article_record(spec,article,listing,TODAY,
                                "https://michinoeki-himawari.com/post-1000/")
        self.assertEqual(why,"accepted")
        self.assertEqual(rec["startDate"],"2026-10-18")
        self.assertEqual(rec["prefecture"],"長崎県")

    def test_nagasaki_old_year_not_reinterpreted_as_current(self):
        from station_discovery_engine import _article_record
        spec={**TOKYO,"roadName":"ひまわり",
              "articleSelector":"article","requiredVenueTokens":["道の駅ひまわり"],
              "useListingPublicationDate":True}
        article=soup("""<article><h1>バイクイベント開催 10月18日(土)</h1>
          <p>場所 道の駅ひまわり</p></article>""")
        listing="2025.10.07 バイクイベント開催 10月18日(土)"
        rec,why=_article_record(spec,article,listing,TODAY,URL)
        self.assertEqual((rec,why),(None,"past"))

    def test_kagoshima_official_upcoming_event_requires_year_and_location(self):
        from station_discovery_engine import _article_record
        spec={**TOKYO,"roadName":"たるみずはまびら","prefecture":"鹿児島県",
              "articleSelector":"article","titleSelectors":["article h1"],
              "requiredVenueTokens":["道の駅たるみずはまびら"],
              "allowedEventWords":["イベント"],"allowExplicitDatedParagraph":True}
        article=soup("""<article><h1>秋の体験イベント</h1>
          <p>道の駅たるみずはまびらにて2026年11月14日(土)に
          イベントを開催します。</p></article>""")
        rec,why=_article_record(spec,article,"秋の体験イベント",TODAY,
                                "https://tarumizuhamabira.jp/information/example/")
        self.assertEqual(why,"accepted")
        self.assertEqual(rec["startDate"],"2026-11-14")
        undated=soup("""<article><h1>秋の体験イベント</h1>
          <p>道の駅たるみずはまびらでの開催日未定</p></article>""")
        rec,why=_article_record(spec,undated,"秋の体験イベント",TODAY,URL)
        self.assertEqual((rec,why),(None,"undated"))

    def test_prefecture_gap_audit_keeps_rejected_article_examples(self):
        spec={**TOKYO,"id":"audit","maxArticles":2}
        listing='<a href="/news/1001">11月イベント開催日未定</a>'
        article='<article><h1>秋のイベント</h1><p>道の駅八王子滝山</p></article>'
        urls={spec["listingUrl"]:listing,
              "https://www.michinoeki-hachioji.net/news/1001":article}
        records,audit=collect_configured_station_events(
            TODAY,[],[spec],fetch=lambda u:soup(urls[u]),report_path=None)
        self.assertEqual(records,[])
        one=audit["sources"][0]
        self.assertEqual(one["accepted"],0)
        self.assertEqual(one["reasons"]["undated"],1)
        self.assertEqual(one["rejectedExamples"][0]["reason"],"undated")
        self.assertIn("/news/1001",one["rejectedExamples"][0]["url"])

    def test_article_css_priority_never_selects_body_first(self):
        from station_discovery_engine import _pick_article
        spec={**TOKYO,"articleSelector":"article, main, .detail, body"}
        detail=soup("""<html><body>
            <h2>サイト共通のイベント情報</h2>
            <article><h1>猿まわし開催</h1><p>記事固有の開催日</p></article>
            <footer>旧イベント 2025年11月11日</footer>
            </body></html>""")
        selected=_pick_article(detail,spec)
        self.assertEqual(selected.name,"article")
        self.assertNotIn("旧イベント",selected.get_text(" ",strip=True))

    def test_osaka_official_div_schedule_with_explicit_dated_row(self):
        from station_discovery_engine import _dated_station_table_records
        spec={**TOKYO, "id":"osaka_table", "prefecture":"大阪府",
              "roadName":"奥河内くろまろの郷",
              "listingUrl":"https://kuromaro.com/event/list/page/4/",
              "allowedHosts":["kuromaro.com"],
              "allowedEventWords":["奥河内くろまろマルシェ"],
              "requireCategoryTokens":["バザール広場イベント"]}
        html="""<main><h1>イベント一覧</h1>
          <div>2026年10月24日～10月25日</div>
          <div>バザール広場イベント</div>
          <div>（全面）第25回　奥河内くろまろマルシェ　1024-1025</div>
          <div>2026年10月31日～10月31日</div>
          <div>周辺施設</div>
          <div>奥河内くろまろマルシェ　別会場</div></main>"""
        found,why=_dated_station_table_records(
            spec,soup(html),TODAY,spec["listingUrl"])
        self.assertEqual(why,"accepted")
        self.assertEqual(len(found),1)
        self.assertEqual((found[0]["startDate"],found[0]["endDate"]),
                         ("2026-10-24","2026-10-25"))

    def test_nagasaki_news_listing_requires_local_year_venue_and_future_date(self):
        from station_discovery_engine import _dated_news_listing_records
        spec={**TOKYO,"id":"himawari_news","prefecture":"長崎県",
              "roadName":"ひまわり",
              "listingUrl":"https://michinoeki-himawari.com/news/",
              "allowedHosts":["michinoeki-himawari.com"],
              "articleMode":"dated_news_listing",
              "requiredVenueTokens":["道の駅ひまわり"],
              "allowedEventWords":["バイクイベント"]}
        html="""<main><h1>お知らせ</h1>
          <h2>バイクイベント開催 １０月１８日(日)</h2>
          <p>2026.10.07</p>
          <p>バイクイベント開催 10月18日(日) 10:00～15:00</p>
          <p>場所 道の駅ひまわり</p>
          <h2>レストラン店休日のお知らせ</h2><p>2026.10.04</p>
          <p>場所　道の駅ひまわり</p>
          </main>"""
        records,audit=collect_configured_station_events(
            TODAY,[],[spec],fetch=lambda _:soup(html),report_path=None)
        self.assertEqual((len(records),audit["newEvents"]),(1,1))
        self.assertEqual(records[0]["startDate"],"2026-10-18")
        self.assertEqual(records[0]["url"],spec["listingUrl"])

    def test_nagasaki_news_body_repeats_headline_without_creating_two_events(self):
        spec={**TOKYO, "roadName":"ひまわり","prefecture":"長崎県",
              "requiredVenueTokens":["道の駅ひまわり"],
              "allowedEventWords":["バイクイベント"]}
        html="""<main>
          <h2>バイクイベント開催 10月18日(日)</h2>
          <p>2026.10.07</p>
          <p>バイクイベント開催 10月18日(日) 10:00～15:00</p>
          <p>場所 道の駅ひまわり</p>
          <h2>レストラン店休日のお知らせ</h2>
          <p>2026.10.04</p>
          <p>場所 道の駅ひまわり</p>
        </main>"""
        from station_discovery_engine import _dated_news_listing_records
        found,why=_dated_news_listing_records(spec,soup(html),TODAY,
                                               "https://michinoeki-himawari.com/news/")
        self.assertEqual(why,"accepted")
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]["title"],"バイクイベント開催 10月18日(日)")

    def test_nagasaki_news_cannot_borrow_venue_from_next_notice(self):
        spec={**TOKYO, "roadName":"ひまわり","prefecture":"長崎県",
              "requiredVenueTokens":["道の駅ひまわり"],
              "allowedEventWords":["バイクイベント"]}
        html="""<main>
          <h2>バイクイベント開催 10月18日(日)</h2>
          <p>2026.10.07</p>
          <p>会場 熊本市民ホール</p>
          <h2>その他のお知らせ</h2>
          <p>2026.10.04</p>
          <p>会場 道の駅ひまわり</p>
        </main>"""
        from station_discovery_engine import _dated_news_listing_records
        records,reason=_dated_news_listing_records(
            spec,soup(html),TODAY,"https://michinoeki-himawari.com/news/")
        self.assertEqual((records,reason),([],"no_strictly_dated_news_notice"))

    def test_nagasaki_news_footer_venue_and_unrelated_post_year_rejected(self):
        from station_discovery_engine import _dated_news_listing_records
        spec={**TOKYO,"requiredVenueTokens":["道の駅ひまわり"],
              "allowedEventWords":["バイクイベント"]}
        html="""<main><h2>バイクイベント開催 10月18日(日)</h2>
           <p>出演者募集中</p><p>10:00～15:00</p>
           <footer><p>場所 道の駅ひまわり</p></footer></main>"""
        found,why=_dated_news_listing_records(spec,soup(html),TODAY,URL)
        self.assertEqual((found,why),([],"no_strictly_dated_news_notice"))

    def test_yamaguchi_separate_heading_for_official_venue(self):
        spec={**TOKYO,"prefecture":"山口県","roadName":"阿武町",
              "requiredVenueTokens":["道の駅阿武町"],
              "allowedEventWords":["森里海の市"],
              "splitArticleTextLines":True,"requireVenueLabel":True}
        html="""<article><h1>令和8年10月11日(日)第48回森里海の市を開催します。</h1>
           <p>■開催日</p><p>開催日:令和8年10月11日(日)</p>
           <p>■開催場所</p><p>道の駅阿武町 〒759-3622</p>
           </article>"""
        rec,why=_article_record(spec,soup(html),"第48回 森里海の市",TODAY,URL)
        self.assertEqual(why,"accepted")
        self.assertEqual(rec["startDate"],"2026-10-11")
        wrong=html.replace("道の駅阿武町 〒759-3622","阿武町役場ホール")
        wrong=wrong.replace("<p>■開催場所</p>","<p>主催：道の駅阿武町</p><p>■開催場所</p>")
        self.assertEqual(_article_record(spec,soup(wrong),"森里海の市",TODAY,URL),
                         (None,"offsite"))

    def test_kumamoto_listing_card_from_official_calendar(self):
        spec={**TOKYO,"id":"aso_calendar","prefecture":"熊本県",
              "roadName":"あそ望の郷くぎの",
              "listingUrl":"https://minamiaso.info/event/?cm=10&cy=2026",
              "allowedHosts":["minamiaso.info"],
              "requiredVenueTokens":["道の駅あそ望の郷くぎの"],
              "allowedEventWords":["青空レストラン"],
              "articleMode":"dated_station_calendar"}
        html="""<main><h1>2026年10月 カレンダー切り替え</h1>
        <div>2026年10月12日</div>
        <h2>第11回 南阿蘇の青空レストラン</h2>
        <div>道の駅あそ望の郷くぎの</div>
        <p>2026年10月12日（月・祝）、キッチンカーが集結するイベント</p>
        <div>2026年10月18日</div>
        <h2>青空レストラン サテライト</h2>
        <div>熊本県野外劇場アスペクタ</div>
        <p>道の駅あそ望の郷くぎのも応援しています</p>
        </main>"""
        records,audit=collect_configured_station_events(
            TODAY,[],[spec],fetch=lambda _:soup(html),report_path=None)
        self.assertEqual(audit["newEvents"],1)
        self.assertEqual(records[0]["startDate"],"2026-10-12")
        self.assertEqual(records[0]["roadName"],"あそ望の郷くぎの")

    def test_kumamoto_calendar_without_local_year_rejected(self):
        from station_discovery_engine import _dated_station_calendar_records
        spec={**TOKYO,"requiredVenueTokens":["道の駅あそ望の郷くぎの"],
              "allowedEventWords":["青空レストラン"]}
        html="""<main><div>10月12日</div>
           <h2>第11回 南阿蘇の青空レストラン</h2>
           <p>道の駅あそ望の郷くぎの</p></main>"""
        rec,why=_dated_station_calendar_records(spec,soup(html),TODAY,URL)
        self.assertEqual((rec,why),([],"no_strict_official_calendar_cards"))

    def test_prefers_specific_venue_event_in_large_city_archive(self):
        spec={**TOKYO,"id":"ehime","listingUrl":"https://www.city.yawatahama.ehime.jp/event/2026/",
              "allowedHosts":["www.city.yawatahama.ehime.jp"],
              "articlePathPattern":r"^/doc/[0-9]+/?$",
              "allowedEventWords":["産業まつり"],
              "preferredTitles":["やわたはま産業まつり"]}
        html="""<a href="/doc/100/">八幡浜市美術館のお知らせ</a>
        <a href="/doc/102/">文化祭予定</a>
        <a href="/doc/103/">第13回やわたはま産業まつりについて</a>"""
        self.assertEqual(list(_links(soup(html),spec))[0],
                         "https://www.city.yawatahama.ehime.jp/doc/103/")

if __name__ == "__main__":
    unittest.main()

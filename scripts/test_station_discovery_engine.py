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
        self.assertEqual(len(rules),7)
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

if __name__ == "__main__":
    unittest.main()

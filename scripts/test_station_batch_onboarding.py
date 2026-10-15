"""Validate batch station-source onboarding against the all-station registry.

This is a safety gate, not evidence that every feed yields events.
"""
import json
import unittest
from datetime import date
from bs4 import BeautifulSoup
from pathlib import Path
from station_discovery_engine import (_validate_sources, _official_url, _links,
                                      collect_configured_station_events)

ROOT=Path(__file__).resolve().parents[1]

class BatchStationOnboardingTests(unittest.TestCase):
    def test_every_source_belongs_to_known_station(self):
        registry=json.loads((ROOT/"data/station_coverage_registry.json").read_text(encoding="utf-8"))
        rules=json.loads((ROOT/"data/station_event_discovery_sources.json").read_text(encoding="utf-8"))
        self.assertEqual(len(registry["stations"]),1234)
        names={(s["prefecture"],s["roadName"]) for s in registry["stations"]}
        _validate_sources(rules["sources"])
        for source in [s for s in rules["sources"] if s["id"] in ("hiroshima_takano", "hiroshima_shinmei")]:
            with self.subTest(id=source["id"]):
                self.assertIn((source["prefecture"],source["roadName"]),names)

    def test_new_hiroshima_feeds_are_separate(self):
        rules=json.loads((ROOT/"data/station_event_discovery_sources.json").read_text(encoding="utf-8"))
        selected=[s for s in rules["sources"] if s["id"] in ("hiroshima_takano","hiroshima_shinmei")]
        self.assertEqual(len(selected),2)
        self.assertEqual({s["roadName"] for s in selected},{"たかの","みはら神明の里"})
        self.assertTrue(all(s["listingUrl"].startswith("https://") for s in selected))

    def test_takano_numeric_articles_only(self):
        rules=json.loads((ROOT/"data/station_event_discovery_sources.json").read_text(encoding="utf-8"))
        source=next(s for s in rules["sources"] if s["id"]=="hiroshima_takano")
        html="""<main>
            <a href="/12619/">『庄原里山マルシェ』in広島駅 開催決定！</a>
            <a href="/12605/">りんご狩り予約開始のお知らせ</a>
            <a href="/news_event/">お知らせ・イベント情報</a>
            <a href="/category/news/">お知らせ</a>
            <a href="https://bad.example/12620/">外部イベントのお知らせ</a>
        </main>"""
        found=_links(BeautifulSoup(html,"html.parser"),source)
        self.assertEqual(set(found),{"https://takanoyama.jp/12619/",
                                      "https://takanoyama.jp/12605/"})
        self.assertTrue(_official_url("https://takanoyama.jp/12619/",source,article=True))
        self.assertFalse(_official_url("https://takanoyama.jp/news_event/",source,article=True))

    def test_shinmei_official_home_only_not_site_navigation(self):
        rules=json.loads((ROOT/"data/station_event_discovery_sources.json").read_text(encoding="utf-8"))
        source=next(s for s in rules["sources"] if s["id"]=="hiroshima_shinmei")
        listing=BeautifulSoup("""<main>
            <a href="michinoekimihara.html">道の駅みはら神明の里</a>
            <a href="features.html">三原の紹介</a>
            <a href="info.html">お問い合わせ</a>
        </main>""","html.parser")
        self.assertEqual(_links(listing,source),
                         {source["listingUrl"]:"公式開催案内"})
        self.assertFalse(_official_url("https://www.shinmeinosato.jp/info.html",
                                       source,article=True))

    def test_shinmei_on_page_notices_require_local_date_and_venue(self):
        rules=json.loads((ROOT/"data/station_event_discovery_sources.json").read_text(encoding="utf-8"))
        source=next(s for s in rules["sources"] if s["id"]=="hiroshima_shinmei")
        def collect(html):
            seen=[]
            def fetch(url):
                seen.append(url)
                return BeautifulSoup(html,"html.parser")
            records,audit=collect_configured_station_events(
                date(2026,10,15),[],[source],fetch=fetch,report_path=None)
            self.assertEqual(seen,[source["listingUrl"]])
            self.assertEqual(audit["sources"][0]["checked"],1)
            return records
        event="""<main><h2>10月25日(日) みはら神明の里感謝祭開催</h2>
            <p>2026.10.14</p>
            <p>10月25日(日) 10:00～15:00</p>
            <p>会場 道の駅みはら神明の里 イベントスペース</p>
            <h2>施設のご案内</h2><p>2026.10.01</p>
            </main><footer>道の駅みはら神明の里</footer>"""
        records=collect(event)
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]["startDate"],"2026-10-25")
        self.assertEqual(records[0]["url"],source["listingUrl"])
        offsite=event.replace("会場 道の駅みはら神明の里 イベントスペース",
                              "会場 三原市役所")
        self.assertEqual(collect(offsite),[])
        undated=event.replace("2026.10.14","10月14日")
        self.assertEqual(collect(undated),[])

if __name__=="__main__": unittest.main()

"""Offline tests: national-directory links are hints, never proof of a station site."""
import json
import unittest
from unittest.mock import patch

from station_official_directory_discovery import (
    BASE, HOST, LIST_BASE, listing_matches, detail_hints, crawl_once, crawl_batch,
    robots_policy, same_directory_url, network_fetch,
)


class OfficialDirectoryPilotTests(unittest.TestCase):
    def setUp(self):
        self.roads = [
            {"id": "RS0001", "prefecture": "北海道", "name": "三笠"},
            {"id": "RS0002", "prefecture": "北海道", "name": "スタープラザ　芦別"},
            {"id": "RS0003", "prefecture": "青森県", "name": "三笠"},
        ]
        self.listing = """<main>
          <a href="/stations/views/18786"><div>三笠</div><p>北海道 三笠市</p></a>
          <a href="/stations/views/18787">スタープラザ　芦別 北海道 芦別市</a>
          <a href="/stations/views/99999">三笠 青森県 別の市</a>
          <a href="/stations/views/12345">偽名 北海道</a>
          <a href="https://evil.example/stations/views/18788">三笠 北海道</a>
        </main>"""
        self.detail = """<h2>道の駅「三笠」</h2>
          <dl><dt>道の駅名</dt><dd>三笠</dd>
          <dt>ホームページ</dt><dd><a href="http://www.hokkaido-michinoeki.jp/michinoeki/172/">駅紹介</a></dd>
          <dt>ホームページ2</dt><dd><a href="https://www.city.mikasa.hokkaido.jp/hotnews/detail/00000036.html">市公式</a></dd></dl>
          <footer><a href="https://evil.example/unrelated">広告</a></footer>"""

    def test_listing_matches_prefecture_and_name_not_near_matches(self):
        rows = listing_matches(self.listing, self.roads)
        self.assertEqual([(x["id"], x["directoryDetailUrl"]) for x in rows], [
            ("RS0001", BASE + "/stations/views/18786"),
            ("RS0002", BASE + "/stations/views/18787"),
            ("RS0003", BASE + "/stations/views/99999"),
        ])

    def test_homepage_fields_are_only_unverified_link_hints(self):
        found = detail_hints(self.detail, {"prefecture": "北海道", "roadName": "三笠"})
        self.assertEqual(len(found), 2)
        self.assertTrue(any("mikasa.hokkaido.jp" in x for x in found))
        self.assertTrue(any(x.startswith("http://") for x in found))
        self.assertFalse(any("evil.example" in x for x in found))
        self.assertIsNone(detail_hints(
            self.detail, {"prefecture": "北海道", "roadName": "南ふらの"}))

    def test_reject_redirected_hosts_and_non_directory_paths(self):
        self.assertTrue(same_directory_url(LIST_BASE+"?page=1"))
        self.assertTrue(same_directory_url(BASE+"/stations/views/18786",detail=True))
        for url in ["http://"+HOST+"/stations/views/18786",
                    "https://evil.example/stations/views/18786",
                    BASE+"/contact", BASE+"/stations/views/../search/10/all/all",
                    "https://usr:password@"+HOST+"/stations/views/18786"]:
            self.assertFalse(same_directory_url(url,detail=True))

    def test_robots_disallow_prevents_crawling(self):
        def fetch(url, robots=False):
            self.assertTrue(robots)
            return 200, "User-agent: *\nDisallow: /stations/"
        allowed = robots_policy(fetch)
        self.assertFalse(allowed(LIST_BASE))
        self.assertTrue(allowed(BASE+"/robots.txt"))
        with self.assertRaisesRegex(RuntimeError, "disallows"):
            crawl_once(lambda url: (200,self.listing),robots_allowed=allowed,
                       max_details=1,scanned_on="2026-10-13")
        with self.assertRaisesRegex(RuntimeError,"unavailable"):
            robots_policy(lambda url,robots=False: (503,""))

    def test_bounded_cursor_and_no_auto_offsite_fetch(self):
        detail2 = self.detail.replace("道の駅「三笠」","道の駅「スタープラザ　芦別」")
        page = """<main>
          <a href="/stations/views/18786">三笠 北海道 三笠市</a>
          <a href="/stations/views/18787">スタープラザ　芦別 北海道 芦別市</a>
          <a href="/stations/search/all/all/all?page=1">2</a>
        </main>"""
        seen=[]
        def fetch(url):
            seen.append(url)
            return 200, {
                LIST_BASE: page,
                BASE+"/stations/views/18786": self.detail,
                BASE+"/stations/views/18787": detail2,
            }[url]
        # Use the exact app master in the first iteration only.
        from station_official_directory_discovery import read_app_stations as real_read
        with patch("station_official_directory_discovery.read_app_stations",
                   return_value=self.roads):
            first=crawl_once(fetch,robots_allowed=lambda x: True,max_details=1,
                             scanned_on="2026-10-13")
            self.assertEqual(first["cursor"],{"page":0,"offset":1})
            self.assertEqual(first["lastRun"]["inspected"],1)
            self.assertEqual(len(first["stations"]),1)
            self.assertFalse(first["stations"][0]["officialSiteOwnershipVerified"])
            second=crawl_once(fetch,robots_allowed=lambda x: True,old=first,max_details=1,
                              scanned_on="2026-10-13")
        self.assertEqual(second["cursor"],{"page":1,"offset":0})
        self.assertEqual(second["lastRun"]["inspected"],1)
        self.assertFalse(second["listingTraversalCompleted"])
        self.assertEqual(len(second["stations"]),2)
        self.assertEqual(seen, [LIST_BASE,BASE+"/stations/views/18786",
                                LIST_BASE,BASE+"/stations/views/18787"])
        self.assertFalse(any("hokkaido-michinoeki.jp" in x for x in seen))

    def test_one_daily_batch_crosses_page_boundary_without_missing_records(self):
        pages = {
            LIST_BASE: ('<main><a href="/stations/views/18786">三笠 北海道 三笠市</a>'
                        '<a href="/stations/views/18787">スタープラザ　芦別 北海道 芦別市</a>'
                        '<a href="/stations/search/all/all/all?page=1">次へ</a></main>'),
            LIST_BASE+"?page=1": (
                '<main><a href="/stations/views/99999">三笠 青森県 別の市</a></main>'),
        }
        fetched=[]
        def fetch(url):
            fetched.append(url)
            if url in pages:
                return 200, pages[url]
            return 200, (self.detail if url.endswith("/18786")
                         else self.detail.replace('道の駅「三笠」',
                             '道の駅「スタープラザ　芦別」' if url.endswith("/18787")
                             else '道の駅「三笠」'))
        with patch("station_official_directory_discovery.read_app_stations",
                   return_value=self.roads):
            x=crawl_batch(fetch,robots_allowed=lambda _:True,max_details=3,
                         scanned_on="2026-10-13")
        self.assertTrue(x["listingTraversalCompleted"])
        self.assertEqual(x["lastRun"]["listingPagesVisited"],2)
        self.assertEqual(x["lastRun"]["examined"],3)
        self.assertEqual(x["lastRun"]["inspected"],3)
        self.assertEqual(len(x["stations"]),3)
        self.assertEqual(x["cursor"],{"page":1,"offset":1})
        self.assertEqual(fetched.count(LIST_BASE+"?page=1"),1)
        self.assertFalse(any("hokkaido-michinoeki.jp" in u for u in fetched))

    def test_national_daily_48_scans_multiple_chunks_of_same_listing_page(self):
        roads = [{"id": "RS%04d" % i, "prefecture": "広島県",
                  "name": "架空駅%03d" % i} for i in range(1, 51)]
        listing = "<main>" + "".join(
            '<a href="/stations/views/%d">架空駅%03d 広島県</a>' % (30000+i, i)
            for i in range(1, 51)) + (
                '<a href="/stations/search/all/all/all?page=1">次ページ</a></main>')
        calls = []
        def fetch(url):
            calls.append(url)
            if url == LIST_BASE:
                return 200, listing
            i = int(url.rsplit("/", 1)[-1]) - 30000
            return 200, '<h2>道の駅「架空駅%03d」</h2>' % i
        with patch("station_official_directory_discovery.read_app_stations",
                   return_value=roads):
            result = crawl_batch(fetch, robots_allowed=lambda _: True,
                                 max_details=48, scanned_on="2026-10-15")
        self.assertEqual(result["cursor"], {"page": 0, "offset": 48})
        self.assertEqual(result["lastRun"]["examined"], 48)
        self.assertEqual(result["lastRun"]["inspected"], 48)
        self.assertEqual(len(result["stations"]), 48)
        self.assertEqual(calls.count(LIST_BASE), 2)
        self.assertFalse(result["listingTraversalCompleted"])

    def test_directory_rate_limit_aborts_instead_of_skipping_station(self):
        listing = '<main><a href="/stations/views/18786">三笠 北海道</a></main>'
        def fetch(url):
            return (200, listing) if url == LIST_BASE else (429, "busy")
        with patch("station_official_directory_discovery.read_app_stations",
                   return_value=self.roads):
            with self.assertRaisesRegex(RuntimeError, "rate-limited"):
                crawl_batch(fetch, robots_allowed=lambda _: True,
                            max_details=1, scanned_on="2026-10-15")
        with self.assertRaises(ValueError):
            crawl_batch(lambda _: None, robots_allowed=lambda _: True,
                        max_details=97)

    def test_end_of_nationwide_listing_marks_complete_and_preserves_error_row(self):
        html='<main><a href="/stations/views/18786">三笠 北海道 三笠市</a></main>'
        with patch("station_official_directory_discovery.read_app_stations",
                   return_value=self.roads):
            data=crawl_once(lambda url: (404,"") if "/views/" in url else (200,html),
                            robots_allowed=lambda _:True,max_details=1,
                            scanned_on="2026-10-13")
        self.assertTrue(data["listingTraversalCompleted"])
        self.assertEqual(data["lastRun"]["errors"],1)
        self.assertEqual(data["stations"][0]["directoryCheckStatus"],"http_404")
        self.assertFalse(data["stations"][0]["officialWebsiteCandidateUrlsUnverified"])
        again=crawl_once(lambda _: self.fail("Completed crawl must not refetch"),
                         robots_allowed=lambda _:True,old=data,max_details=1)
        self.assertTrue(again["listingTraversalCompleted"])

    def test_list_mismatch_is_error_not_false_completion(self):
        with patch("station_official_directory_discovery.read_app_stations",
                   return_value=self.roads):
            with self.assertRaisesRegex(RuntimeError, "has no exact master matches"):
                crawl_once(lambda url: (200,"<main>サーバ更新中</main>"),
                           robots_allowed=lambda x: True,max_details=1,
                           scanned_on="2026-10-13")

    def test_only_approved_fetch_urls_can_be_network_requested(self):
        class FakeSession:
            def get(self,url,**kwargs):
                return type("Res",(),{"status_code":200,"text":"OK","content":b"OK"})()
        fetch=network_fetch(FakeSession())
        with self.assertRaises(ValueError):
            fetch("https://evil.example/")
        with self.assertRaises(ValueError):
            fetch(BASE+"/stations/views/18786/../admin")
        self.assertEqual(fetch(LIST_BASE), (200,"OK"))
        self.assertEqual(fetch(BASE+"/stations/views/18786"), (200,"OK"))


if __name__ == "__main__":
    unittest.main()

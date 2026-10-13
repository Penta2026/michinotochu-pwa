import unittest
from nationwide_source_audit import scan_event_listing, match_station_hints, SECONDARY_EVENT_LISTINGS

class FakeResponse:
    def __init__(self, code, body):
        self.status_code = code
        self.text = body
        self.content = body.encode("utf-8")

class NationwideEventCategoryTests(unittest.TestCase):
    def test_official_category_candidates_are_only_hints(self):
        urls = []
        def fetch(url, **kwargs):
            urls.append(url)
            if url.endswith("/robots.txt"):
                return FakeResponse(200, "User-agent: *\nAllow: /")
            return FakeResponse(200, '<a href="/archives/2026/event/">道の駅秋のイベント開催</a>'
                                     '<a href="https://external.example/event/">道の駅祭り開催</a>')
        result = scan_event_listing("https://www.kanto-michinoeki.jp/archives/category/event", fetch)
        self.assertEqual(result["state"], "inspected")
        self.assertEqual(result["candidateCount"], 1)
        self.assertEqual(len(urls), 2)

    def test_robots_denial_stops_before_category_fetch(self):
        calls = []
        def fetch(url, **kwargs):
            calls.append(url)
            return FakeResponse(200, "User-agent: *\nDisallow: /archives/")
        result = scan_event_listing("https://www.kanto-michinoeki.jp/archives/category/event", fetch)
        self.assertEqual(result["state"], "robots_disallowed")
        self.assertEqual(len(calls), 1)

    def test_robots_failure_is_not_permission(self):
        def fetch(url, **kwargs):
            return FakeResponse(503, "temporary")
        result = scan_event_listing("https://www.kanto-michinoeki.jp/archives/category/event", fetch)
        self.assertEqual(result["state"], "robots_unknown")

class StationHintTests(unittest.TestCase):
    def test_three_regions_have_secondary_discovery_sources(self):
        self.assertTrue({"関東", "北陸", "九州・沖縄"}.issubset(SECONDARY_EVENT_LISTINGS))


    def test_matches_station_without_claiming_event(self):
        audit = {"sources": [{"region": "関東", "candidates": [
            {"title": "【こすげ】秋のマルシェ開催", "url": "https://example.org/article"}]}]}
        roads = [{"id": "RS100", "prefecture": "山梨県", "name": "こすげ"}]
        entry = match_station_hints(audit, roads)["sources"][0]["candidates"][0]
        self.assertEqual(entry["stationIdHint"], "RS100")
        self.assertFalse(entry["eventVerified"])

    def test_ambiguous_name_not_assigned(self):
        audit = {"sources": [{"region": "全国", "candidates": [
            {"title": "【共通駅】イベント開催"}]}]}
        roads = [{"id": "A", "prefecture": "山梨県", "name": "共通駅"},
                 {"id": "B", "prefecture": "埼玉県", "name": "共通駅"}]
        entry = match_station_hints(audit, roads)["sources"][0]["candidates"][0]
        self.assertEqual(entry["identityStatus"], "ambiguous")
        self.assertEqual(entry["stationIdHint"], "")

if __name__ == "__main__":
    unittest.main()

import unittest
from nationwide_source_audit import scan_event_listing

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

if __name__ == "__main__":
    unittest.main()

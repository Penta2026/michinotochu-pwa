"""Offline tests: broad website triage must never publish unverified events."""
import unittest
from station_source_triage import build, render_markdown


class NationalSourceTriageTests(unittest.TestCase):
    def test_source_hints_are_ranked_not_promoted(self):
        queue = {"stations": [
            {"id": "RS0010", "prefecture": "広島県", "roadName": "仮の駅A",
             "directoryInspectionState": "checked",
             "candidates": [{"url": "https://hiroshima.example/",
                             "kind": "station_or_partner_site_unverified"}]},
            {"id": "RS0011", "prefecture": "福井県", "roadName": "仮の駅B",
             "directoryInspectionState": "checked",
             "candidates": [{"url": "https://fukui.example/",
                             "kind": "station_or_partner_site_unverified"}]},
            {"id": "RS0012", "prefecture": "山形県", "roadName": "既存駅",
             "directoryInspectionState": "checked",
             "candidates": [{"url": "https://known.example/",
                             "kind": "station_or_partner_site_unverified"}]},
            {"id": "RS0013", "prefecture": "福井県", "roadName": "偽物候補",
             "directoryInspectionState": "not_checked",
             "candidates": [{"url": "https://evil.example/",
                             "kind": "station_or_partner_site_unverified"}]},
        ]}
        audit = {"checkedAt": "2026-10-15T00:00:00Z", "results": [
            {"stationId": "RS0010", "url": "https://hiroshima.example/",
             "status": "identity_mentioned_unverified", "stationNameMentioned": True,
             "eventLinkHints": ["https://hiroshima.example/events/", "https://evil.example/events/"]},
            {"stationId": "RS0011", "url": "https://fukui.example/",
             "status": "identity_mentioned_unverified", "stationNameMentioned": True,
             "eventLinkHints": ["/news/", "http://fukui.example/news", "https://fukui.example:443/foo"]},
            {"stationId": "RS0012", "url": "https://known.example/",
             "status": "identity_mentioned_unverified", "stationNameMentioned": True,
             "eventLinkHints": ["/event/"]},
            {"stationId": "RS0013", "url": "https://evil.example/",
             "status": "identity_mentioned_unverified", "stationNameMentioned": True,
             "eventLinkHints": ["/event/"]},
            {"stationId": "RS9999", "url": "https://fake.example/",
             "status": "identity_mentioned_unverified", "stationNameMentioned": True,
             "eventLinkHints": ["/event/"]},
        ]}
        config = {"sources": [{"prefecture": "山形県", "roadName": "既存駅", "enabled": True}]}
        coverage = {"prefectures": [{"prefecture": "福井県", "eventCount": 0},
                                    {"prefecture": "広島県", "eventCount": 3}]}
        result = build(queue, audit, config, coverage, limit=50)
        self.assertEqual([x["stationId"] for x in result["shortlist"]], ["RS0011", "RS0010"])
        self.assertEqual(result["potentialEventListingSites"], 2)
        self.assertEqual(result["shortlist"][0]["eventLinkHints"], ["https://fukui.example/news/"])
        self.assertEqual(result["shortlist"][1]["eventLinkHints"], ["https://hiroshima.example/events/"])
        self.assertTrue(all(not x["readyForPublishing"] for x in result["shortlist"]))
        self.assertTrue(all(not x["officialSiteOwnershipVerified"] for x in result["shortlist"]))
        self.assertIn("公式サイト確定・イベント登録の台帳ではない", render_markdown(result))

    def test_review_status_and_prior_source_scope_are_enforced(self):
        station = {"id": "RS0010", "prefecture": "広島県", "roadName": "テスト駅",
                   "directoryInspectionState": "checked",
                   "candidates": [{"url": "https://station.example/",
                                   "kind": "station_or_partner_site_unverified"}]}
        queue = {"stations": [station]}
        audit = {"results": [
            {"stationId": "RS0010", "url": "https://station.example/",
             "status": "identity_mentioned_unverified", "stationNameMentioned": True,
             "eventLinkHints": ["/news"]},
            {"stationId": "RS0010", "url": "https://station.example/",
             "status": "identity_not_found", "stationNameMentioned": False,
             "eventLinkHints": ["/news"]},
            {"stationId": "RS0010", "url": "https://intruder.example/",
             "status": "identity_mentioned_unverified", "stationNameMentioned": True,
             "eventLinkHints": ["/news"]},
        ]}
        result = build(queue, audit, {"sources": []}, {"prefectures": []})
        self.assertEqual(result["shortlisted"], 0)
        with self.assertRaises(ValueError):
            build(queue, audit, {}, {}, limit=51)
        with self.assertRaises(ValueError):
            build({"stations": [station, station]}, audit, {}, {})


if __name__ == "__main__":
    unittest.main()

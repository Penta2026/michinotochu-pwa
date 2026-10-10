"""Offline regression tests for conservative collection-gap monitoring."""
import unittest

from road_event_gap_monitor import make_report, render_dashboard, parse_app_station_master

TODAY = "2026-10-11"


def source(**kw):
    s = {
        "id": "tokyo_station", "prefecture": "東京都", "roadName": "八王子滝山",
        "listingUrl": "https://official.example/events/",
        "candidates": 4, "checked": 4, "accepted": 0,
        "reconfirmed": 0, "knownSkipped": 0, "fetchFailed": 0,
        "fetchErrors": [], "listingError": "", "reasons": {},
        "rejectedExamples": [],
    }
    s.update(kw)
    return s


class GapMonitorTests(unittest.TestCase):
    def config(self, **kw):
        s = {"id": "tokyo_station", "enabled": True, "prefecture": "東京都",
             "roadName": "八王子滝山",
             "listingUrl": "https://official.example/events/",
             "maxArticles": 6}
        s.update(kw)
        return {"sources": [s]}

    def coverage(self):
        return {
            "summary": {"historicalObservedPrefectures": 47,
                        "observedPrefectures": 44,
                        "registeredEvents": 78,
                        "targetedStationFeedPrefectures": 25},
            "historical": {"previouslyObservedWithoutCurrentEvents":
                           ["滋賀県", "鳥取県", "徳島県"]},
            "prefectures": [
                {"prefecture": "東京都", "observedStations": ["八王子滝山"],
                 "targetedStationFeeds": ["八王子滝山"]},
                {"prefecture": "北海道", "observedStations": ["たきかわ"],
                 "targetedStationFeeds": []},
            ],
        }

    def report(self, entry=None, *, previous=None, today=TODAY, registry=None,
               regional=None):
        return make_report(
            {"schemaVersion": 1, "checkedOn": today,
             "sources": [entry or source()]},
            registry or self.config(), self.coverage(),
            {"notReconfirmed": []},
            regional if regional is not None else {"sources": [
                {"region": "関東", "status": "discovery",
                 "candidateCount": 0, "reachable": True}]},
            previous=previous, today=today)

    def test_event_candidates_need_review_not_auto_publication(self):
        entry = source(
            reasons={"undated": 1, "venue_missing": 1, "past": 1,
                     "offsite": 1, "not_event": 1},
            rejectedExamples=[
                {"title": "秋のマルシェ", "url": "https://official.example/a",
                 "reason": "undated"},
                {"title": "秋の催し", "url": "https://official.example/b",
                 "reason": "venue_missing"},
                {"title": "夏祭り", "url": "https://official.example/c",
                 "reason": "past"},
                {"title": "市役所ホールのまつり", "url": "https://official.example/d",
                 "reason": "offsite"},
                {"title": "10月イベントカレンダー",
                 "url": "https://official.example/e", "reason": "not_event"},
                {"title": "10月イベントカレンダー",
                 "url": "https://official.example/e", "reason": "not_event"},
            ])
        report = self.report(entry)
        queue = report["reviewCandidates"]
        self.assertEqual(len(queue), 3)
        self.assertEqual({x["reviewReason"] for x in queue},
                         {"event_date_unverified", "onsite_venue_unverified",
                          "calendar_announcement_needs_detail"})
        self.assertTrue(all(x["status"] == "unverified_candidate" for x in queue))
        self.assertEqual(report["summary"]["rejectedReasonCounts"]["offsite"], 1)
        self.assertIn("not all rejected articles", report["limitations"]["reviewQueue"])

    def test_source_fetch_issue_is_visible_and_persists_across_days(self):
        failed = source(candidates=1, checked=0, fetchFailed=1,
                        fetchErrors=[{"type": "HTTPError", "detail": "404"}])
        first = self.report(failed)
        self.assertEqual(first["summary"]["sourcesWithFetchProblems"], 1)
        self.assertEqual(first["sources"][0]["failureDayStreak"], 1)
        self.assertEqual(first["sources"][0]["fetchErrors"][0]["detail"], "404")
        second = self.report(failed, previous=first, today=TODAY)
        self.assertEqual(second["sources"][0]["failureDayStreak"], 1)
        next_day = self.report(failed, previous=second, today="2026-10-12")
        self.assertEqual(next_day["sources"][0]["failureDayStreak"], 2)
        fixed = self.report(source(), previous=next_day, today="2026-10-13")
        self.assertEqual(fixed["sources"][0]["failureDayStreak"], 0)

    def test_no_candidate_warning_only_after_three_distinct_days(self):
        entry = source(candidates=0, checked=0)
        a = self.report(entry, today="2026-10-11")
        self.assertEqual(a["summary"]["sourcesWithZeroCandidates"], 1)
        self.assertFalse(any(w["kind"] == "repeatedly_empty_listing"
                             for w in a["warnings"]))
        b = self.report(entry, previous=a, today="2026-10-12")
        c = self.report(entry, previous=b, today="2026-10-13")
        self.assertEqual(c["sources"][0]["emptyCandidateDayStreak"], 3)
        self.assertTrue(any(w["kind"] == "repeatedly_empty_listing"
                            for w in c["warnings"]))
        self.assertFalse(any(w["kind"] == "source_fetch_error"
                             for w in c["warnings"]))

    def test_article_cap_surfaces_possible_uninspected_candidates(self):
        entry = source(candidates=21, checked=6)
        report = self.report(entry)
        self.assertEqual(report["summary"]["sourcesAtCheckLimit"], 1)
        self.assertTrue(report["sources"][0]["mayHaveUnreviewedCandidates"])
        self.assertTrue(any(w["kind"] == "article_check_limit"
                            for w in report["warnings"]))
        # Previously published URL skips explain unmatched candidate counts.
        no_alert = self.report(source(candidates=21, checked=6, knownSkipped=15))
        self.assertEqual(no_alert["summary"]["sourcesAtCheckLimit"], 0)

    def test_published_without_direct_source_is_not_called_unmonitored(self):
        report = self.report()
        self.assertEqual(report["summary"]["publishedStations"], 2)
        self.assertEqual(report["summary"]["publishedStationsWithoutDirectTarget"], 1)
        self.assertEqual(report["publishedStationsWithoutDirectTarget"][0]["roadName"],
                         "たきかわ")
        self.assertEqual(report["publishedStationsWithoutDirectTarget"][0]["status"],
                         "published_through_other_collector_not_unmonitored")
        self.assertIn("No complete nationwide station master",
                      report["limitations"]["stationCoverage"])
        self.assertIn("unknown", report["limitations"]["eventRecall"])
        self.assertEqual(report["historicallyReachedWithNoCurrentEvents"],
                         ["滋賀県", "鳥取県", "徳島県"])

    def test_missing_and_stale_discovery_audits_are_reported(self):
        report = make_report(
            {"checkedOn": "2026-10-10", "sources": []},
            self.config(), self.coverage(), {}, {"sources": []}, today=TODAY)
        problems = {w["kind"] for w in report["warnings"]}
        self.assertIn("stale_discovery_audit", problems)
        self.assertIn("configured_source_not_audited", problems)
        self.assertFalse(report["summary"]["phase2AuditFresh"])

    def test_unreachable_regional_homepage_is_not_mistaken_for_factual_no_events(self):
        report = self.report(regional={"sources": [
            {"region": "北海道", "reachable": False, "status": "discovery",
             "candidateCount": 0}]})
        self.assertTrue(any(w["kind"] == "regional_homepage_unreachable"
                            for w in report["warnings"]))
        self.assertEqual(report["regionalHomepages"][0]["homepageReachable"], False)
        self.assertIn("does NOT prove", report["regionalHomepages"][0]["note"])

    def test_markdown_dashboard_is_readable_and_does_not_overstate_coverage(self):
        report = self.report(source(
            candidates=1, checked=0, fetchFailed=1,
            fetchErrors=[{"type": "HTTPError", "detail": "404"}],
            reasons={"undated": 1},
            rejectedExamples=[{"title": "開催日不明のマルシェ",
                               "url": "https://official.example/a",
                               "reason": "undated"}]))
        text = render_dashboard(report)
        self.assertIn("取りこぼし監視ダッシュボード", text)
        self.assertIn("source_fetch_error", text)
        self.assertIn("イベントかどうかは未確認", text)
        self.assertIn("開催日不明のマルシェ", text)
        self.assertIn("駅マスタ未接続", text)
        self.assertIn("47", text)

    def test_in_app_master_json_assignment_is_parsed_without_running_js(self):
        text = ('window.DATA_META={"roadStations":2};\n'
                'window.APP_DATA={"meta":{"roadStations":2,"generated":"2026-10-04"},'
                '"roads":[{"id":"RS001","prefecture":"東京都","name":"八王子滝山"},'
                '{"id":"RS002","prefecture":"北海道","name":"たきかわ"}]};\n')
        parsed = parse_app_station_master(text)
        self.assertEqual(len(parsed["stations"]), 2)
        self.assertEqual(parsed["stations"][0]["roadName"], "八王子滝山")
        self.assertEqual(parsed["generated"], "2026-10-04")
        self.assertRaises(ValueError, parse_app_station_master,
                          text.replace('"roadStations":2,"generated"',
                                       '"roadStations":3,"generated"'))
        self.assertRaises(ValueError, parse_app_station_master,
                          text.replace('"id":"RS002"', '"id":"RS001"'))

    def test_in_app_master_exposes_no_dedicated_source_without_claiming_blindness(self):
        station_master = {
            "generated": "2026-10-04", "version": "2.8.20",
            "stations": [
                {"id": "RS001", "prefecture": "東京都", "roadName": "八王子滝山"},
                {"id": "RS002", "prefecture": "北海道", "roadName": "たきかわ"},
                {"id": "RS003", "prefecture": "東京都", "roadName": "東京もう一つの駅"},
            ],
        }
        report = make_report(
            {"checkedOn": TODAY, "sources": [source()]},
            self.config(), self.coverage(), {"notReconfirmed": []},
            {"sources": []}, today=TODAY, station_master=station_master)
        self.assertEqual(report["summary"]["appMasterStations"], 3)
        self.assertEqual(report["summary"]["appMasterWithDedicatedSource"], 1)
        self.assertEqual(report["summary"]["appMasterWithoutDedicatedSource"], 2)
        self.assertEqual(report["summary"]["appMasterCurrentlyPublishedStations"], 2)
        self.assertEqual(report["appMasterStations"][1]["status"],
                         "published_by_other_collectors")
        self.assertEqual(report["appMasterStations"][2]["status"],
                         "no_dedicated_source")
        dashboard = render_dashboard(report)
        self.assertIn("アプリ内駅マスタと個別公式収集先の照合", dashboard)
        self.assertIn("地域連絡会などから拾える場合", dashboard)
        self.assertIn("東京もう一つの駅", str(report["appMasterStations"]))

    def test_unconfirmed_items_are_retained_as_review_only(self):
        record = {"roadName": "阿武町", "title": "森里海の市",
                  "url": "https://official.example/abu",
                  "startDate": "2026-11-29", "endDate": "2026-11-29"}
        report = make_report(
            {"checkedOn": TODAY, "sources": [source()]},
            self.config(), self.coverage(), {"notReconfirmed": [record]},
            {"sources": []}, today=TODAY)
        self.assertEqual(report["summary"]["unreconfirmedEvents"], 1)
        self.assertEqual(report["unreconfirmedEvents"][0]["status"],
                         "needs_reconfirmation")


if __name__ == "__main__":
    unittest.main()

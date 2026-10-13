import unittest
from national_event_source_priority import make_report, attach_station_source_health, attach_regional_adapter_health, standardize_nine_region_audits, format_dashboard

class NationwidePriorityTests(unittest.TestCase):
    def test_region_gap_does_not_claim_no_events_or_verified_coverage(self):
        coverage = {"summary": {"observedPrefectures": 36, "zeroRegisteredPrefectures": 11},
                    "regions": [{"region": "北陸", "prefectureCount": 3, "zeroRegisteredPrefectures": ["富山県"],
                                 "registeredEventCount": 4}]}
        audit = {"sources": [{"region": "北陸", "reachable": True, "status": "discovery",
                              "url": "https://example.org", "candidateCount": 3}]}
        result = make_report(coverage, audit)
        self.assertEqual(result["regions"][0]["nextAction"], "verify_event_listing_and_build_safe_adapter")
        self.assertEqual(result["regions"][0]["prefecturesWithoutCurrentPublishedEvents"], ["富山県"])
        self.assertEqual(result["highTrafficStationPriority"]["state"], "awaiting_objective_visitation_evidence")
        self.assertIsNone(result["regions"][0]["regionalArticleAccepted"])
        self.assertIn("広域サイト監査結果", format_dashboard(result))

    def test_prefecture_evidence_count(self):
        coverage = {"summary": {"observedPrefectures": 0, "zeroRegisteredPrefectures": 1},
                    "regions": [{"region": "北陸", "prefectureCount": 1,
                                 "zeroRegisteredPrefectures": ["富山県"], "registeredEventCount": 0}],
                    "prefectures": [{"prefecture": "富山県", "reportingRegion": "北陸",
                                     "eventCount": 0, "targetedStationFeeds": [],
                                     "regionalHomepageReachable": True}]}
        audit = {"sources": [{"region": "北陸", "reachable": True, "status": "discovery"}]}
        result = make_report(coverage, audit)
        self.assertEqual(result["prefectureEvidenceCount"], 1)
        self.assertEqual(result["regions"][0]["prefectureEvidence"][0]["evidenceLevel"],
                         "regional_homepage_only_or_unknown")

    def test_dedicated_audit_keeps_errors_and_publication_distinct(self):
        coverage = {"summary": {"observedPrefectures": 0, "zeroRegisteredPrefectures": 1},
                    "regions": [{"region": "北陸", "prefectureCount": 1,
                                 "zeroRegisteredPrefectures": ["富山県"],
                                 "registeredEventCount": 0}],
                    "prefectures": [{"prefecture": "富山県", "reportingRegion": "北陸",
                                     "eventCount": 0, "targetedStationFeeds": []}]}
        report = make_report(coverage, {"sources": []})
        audit = {"checkedOn": "2026-10-13", "sources": [{
            "prefecture": "富山県", "candidates": 7, "checked": 3, "accepted": 1,
            "fetchFailed": 2, "knownSkipped": 1, "listingError": ""}]}
        updated = attach_station_source_health(report, audit)
        pref = updated["regions"][0]["prefectureEvidence"][0]
        self.assertEqual(pref["candidateArticles"], 7)
        self.assertEqual(pref["articlesUnverified"], 3)
        self.assertEqual(pref["sourcesWithFetchProblems"], 1)
        self.assertEqual(pref["articlesAcceptedByDiscovery"], 1)
        self.assertEqual(pref["currentPublishedEvents"], 0)
        self.assertIn("富山県", format_dashboard(updated))

    def test_three_regional_adapter_metrics_are_not_published_counts(self):
        coverage = {"summary": {"observedPrefectures": 0, "zeroRegisteredPrefectures": 0},
                    "regions": [{"region": x, "prefectureCount": 1,
                                 "zeroRegisteredPrefectures": [], "registeredEventCount": 0}
                                for x in ("関東", "北陸", "九州・沖縄")]}
        report = make_report(coverage, {"sources": []})
        attach_regional_adapter_health(report, {
            "北陸": {"pages": [{"staticMatched": 1, "browserMatched": 2, "browserError": ""}], "duplicateCards": 2, "browserRenderedPages": 1},
            "九州・沖縄": {"sources": [{"candidates": 5, "failed": 1, "accepted": 1}], "accepted": 1},
            "関東": {"candidateCount": 4, "acceptedByAdapter": 1, "articleFetchSucceeded": 2, "articleFetchFailed": 1, "decisions": []}})
        by_region = {x["region"]: x for x in report["regions"]}
        self.assertEqual(by_region["北陸"]["adapterAudit"]["candidateMatches"], 3)
        self.assertEqual(by_region["九州・沖縄"]["adapterAudit"]["fetchProblems"], 1)
        self.assertEqual(by_region["九州・沖縄"]["adapterAudit"]["articleChecked"], 0)
        self.assertEqual(by_region["関東"]["adapterAudit"]["acceptedByAdapter"], 1)
        self.assertEqual(by_region["関東"]["currentPublishedEventCount"], 0)
        standardize_nine_region_audits(report)
        self.assertIsNone(by_region["北陸"]["collectionHealth"]["adapterAccepted"])
        self.assertEqual(by_region["関東"]["collectionHealth"]["adapterAccepted"], 1)
        self.assertEqual(by_region["関東"]["collectionHealth"]["articleChecked"], 2)
        self.assertIsNone(by_region["北陸"]["collectionHealth"]["articleChecked"])
        self.assertEqual(by_region["北陸"]["collectionHealth"]["duplicateCards"], 2)
        self.assertEqual(by_region["北陸"]["collectionHealth"]["browserRenderedPages"], 1)
        self.assertEqual(by_region["関東"]["collectionHealth"]["articleFetchSucceeded"], 2)
        self.assertEqual(by_region["関東"]["collectionHealth"]["articleFetchFailed"], 1)
        self.assertIsNone(by_region["九州・沖縄"]["collectionHealth"]["lastSuccessfulCollectionAt"])

    def test_kinki_and_chubu_source_evidence(self):
        coverage = {"summary": {"observedPrefectures": 0, "zeroRegisteredPrefectures": 0},
                    "regions": [{"region": n, "prefectureCount": 1,
                                 "zeroRegisteredPrefectures": [], "registeredEventCount": 0}
                                for n in ("近畿", "中部")]}
        report = make_report(coverage, {"sources": []})
        attach_regional_adapter_health(report, {
            "近畿": {"sources": [{"candidates": 5, "checked": 3, "accepted": 1,
                                "undated": 2, "listingError": ""}], "accepted": 1},
            "中部": {"pages": [{"dated_rows": ["10月1日", "10月2日"]}]}})
        standardize_nine_region_audits(report)
        region = {r["region"]: r["collectionHealth"] for r in report["regions"]}
        self.assertEqual(region["近畿"]["articleChecked"], 3)
        self.assertEqual(region["近畿"]["adapterAccepted"], 1)
        self.assertEqual(region["中部"]["datedPdfRows"], 2)
        self.assertIsNone(region["中部"]["adapterAccepted"])

    def test_hokkaido_audit_uses_actual_check_count(self):
        coverage = {"summary": {"observedPrefectures": 0, "zeroRegisteredPrefectures": 0},
                    "regions": [{"region": "北海道", "prefectureCount": 1,
                                 "zeroRegisteredPrefectures": [], "registeredEventCount": 0}]}
        report = make_report(coverage, {"sources": []})
        attach_regional_adapter_health(report, {"北海道": {
            "candidateCount": 7, "articleChecked": 5,
            "acceptedByAdapter": 2, "fetchFailed": 1, "dateUnverified": 2}})
        standardize_nine_region_audits(report)
        health = report["regions"][0]["collectionHealth"]
        self.assertEqual(health["articleChecked"], 5)
        self.assertEqual(health["adapterAccepted"], 2)
        self.assertEqual(health["adapterCandidates"], 7)
        self.assertIsNone(health["lastSuccessfulCollectionAt"])

    def test_remaining_three_region_audits(self):
        names = ("東北", "中国", "四国")
        coverage = {"summary": {"observedPrefectures": 0, "zeroRegisteredPrefectures": 0},
                    "regions": [{"region": n, "prefectureCount": 1,
                                 "zeroRegisteredPrefectures": [], "registeredEventCount": 0}
                                for n in names]}
        report = make_report(coverage, {"sources": []})
        attach_regional_adapter_health(report, {
            "東北": {"namiokaCandidates": 4, "namiokaArticlesChecked": 3,
                     "acceptedByAdapter": 1, "otherCollectorFailures": ["村田"]},
            "中国": {"candidateArticles": 6, "acceptedByAdapter": 2,
                     "invalid_date": 2},
            "四国": {"candidateCards": 5, "pagesChecked": 2,
                     "acceptedByAdapter": 3}})
        standardize_nine_region_audits(report)
        h = {r["region"]: r["collectionHealth"] for r in report["regions"]}
        self.assertEqual(h["東北"]["articleChecked"], 3)
        self.assertEqual(h["東北"]["adapterFetchProblems"], 1)
        self.assertIsNone(h["中国"]["articleChecked"])
        self.assertEqual(h["中国"]["adapterAccepted"], 2)
        self.assertEqual(h["四国"]["adapterCandidates"], 5)

    def test_missing_audits_are_not_claimed_as_adapter_evidence(self):
        coverage = {"summary": {"observedPrefectures": 0, "zeroRegisteredPrefectures": 0},
                    "regions": [{"region": n, "prefectureCount": 1,
                                 "zeroRegisteredPrefectures": [], "registeredEventCount": 0}
                                for n in ("北陸", "九州・沖縄")]}
        report = make_report(coverage, {"sources": []})
        attach_regional_adapter_health(report, {})
        standardize_nine_region_audits(report)
        for r in report["regions"]:
            self.assertEqual(r["collectionHealth"]["auditEvidence"], "regional_links_only")
            self.assertIsNone(r["collectionHealth"]["adapterAccepted"])

    def test_failed_article_fetch_not_counted_as_checked(self):
        coverage = {"summary": {"observedPrefectures": 0, "zeroRegisteredPrefectures": 0},
                    "regions": [{"region": "関東", "prefectureCount": 1,
                                 "zeroRegisteredPrefectures": [], "registeredEventCount": 0}]}
        report = make_report(coverage, {"sources": []})
        attach_regional_adapter_health(report, {"関東": {
            "candidateCount": 3, "articleFetchSucceeded": 1,
            "articleFetchFailed": 1, "decisions": [
                {"reason": "station_unmatched"}, {"reason": "article_fetch_failed"},
                {"reason": "onsite_venue_unverified"}]}})
        standardize_nine_region_audits(report)
        self.assertEqual(report["regions"][0]["collectionHealth"]["articleChecked"], 1)

    def test_unreachable_source_gets_first_priority(self):
        coverage = {"summary": {"observedPrefectures": 1, "zeroRegisteredPrefectures": 1},
                    "regions": [{"region": "東北", "prefectureCount": 1,
                                 "zeroRegisteredPrefectures": [], "registeredEventCount": 3},
                                {"region": "北海道", "prefectureCount": 1,
                                 "zeroRegisteredPrefectures": ["北海道"], "registeredEventCount": 0}]}
        audit = {"sources": [{"region": "東北", "reachable": True, "status": "adapter"},
                             {"region": "北海道", "reachable": False, "status": "discovery"}]}
        self.assertEqual(make_report(coverage, audit)["regions"][0]["region"], "北海道")

if __name__ == "__main__":
    unittest.main()

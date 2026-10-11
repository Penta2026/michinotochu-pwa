"""Offline tests of independent official-source notice cross-checks."""
import unittest

from road_event_recall_audit import (
    _station_from_title, fetch_national, make_report, parse_national_notices,
    render_dashboard, reviewed_sample,
)

DAY = "2026-10-11"
URL = "https://www.kanto-michinoeki.jp/archives/18237.html"
PDF = "https://official.example/events.pdf"
MASTER = {"stations": [
    {"id": "A", "prefecture": "埼玉県", "roadName": "庄和"},
    {"id": "B", "prefecture": "山梨県", "roadName": "こすげ"},
    {"id": "C", "prefecture": "三重県", "roadName": "飯高駅"},
    {"id": "D", "prefecture": "滋賀県", "roadName": "同名の駅"},
    {"id": "E", "prefecture": "徳島県", "roadName": "同名の駅"},
]}
PUBLISHED = [{
    "prefecture": "埼玉県", "roadName": "庄和",
    "title": "【道の駅庄和】わくわく体験イベント",
    "startDate": "2026-10-31", "endDate": "2026-11-01", "url": URL,
}]
REGIONAL = {"sources": [
    {"region": "関東", "url": "https://www.kanto-michinoeki.jp/",
     "reachable": True,
     "candidates": [
         {"title": "【道の駅庄和】わくわく体験イベント", "url": URL},
         {"title": "【道の駅こすげ】2026年10月25日開催 秋まつり",
          "url": "https://www.kanto-michinoeki.jp/archives/99999.html"},
         {"title": "イベント情報", "url": "https://www.kanto-michinoeki.jp/events/"}
     ]}
]}
NATIONAL = {"name": "全国道の駅連絡会",
            "url": "https://www.michi-no-eki.jp/notices",
            "reachable": True, "candidates": []}
EMPTY_LEDGER = {"schemaVersion": 1, "reviews": []}


def positive(**extra):
    value = {
        "decision": "confirmed_on_site", "reviewedOn": DAY,
        "officialUrl": URL,
        "prefecture": "埼玉県", "roadName": "庄和",
        "title": "【道の駅庄和】わくわく体験イベント",
        "startDate": "2026-10-31", "endDate": "2026-11-01",
        "dateEvidence": "開催日: 2026年10月31日～11月1日",
        "venueEvidence": "会場: 道の駅庄和 情報館",
    }
    value.update(extra)
    return value


class IndependentRecallTests(unittest.TestCase):
    def report(self, *, regional=None, national=None, published=None, ledger=None):
        return make_report(
            REGIONAL if regional is None else regional,
            NATIONAL if national is None else national,
            MASTER, PUBLISHED if published is None else published,
            EMPTY_LEDGER if ledger is None else ledger, DAY)

    def test_national_only_accepts_official_article_links(self):
        html = """<nav><a href="/notices">一覧</a></nav>
          <a href="/notices/views/23233">〖道の駅神鍋高原〗秋祭り</a>
          <a href="/notices/views/23233">duplicate</a>
          <a href="https://evil.example/notices/views/123">external</a>
          <a href="/notices/views/no">invalid</a>"""
        records = parse_national_notices(html)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["url"],
                         "https://www.michi-no-eki.jp/notices/views/23233")
        self.assertEqual(records[0]["title"], "〖道の駅神鍋高原〗秋祭り")

    def test_national_failed_fetch_is_warning_not_fake_empty_success(self):
        source = fetch_national(fetch=lambda _: (_ for _ in ()).throw(
            ValueError("blocked")))
        self.assertFalse(source["reachable"])
        self.assertEqual(source["candidateCount"], 0)
        self.assertIn("ValueError", source["error"])

    def test_station_names_require_unambiguous_bracketed_match(self):
        self.assertEqual(
            _station_from_title("【道の駅庄和】わくわく体験イベント", MASTER)["roadName"],
            "庄和")
        self.assertEqual(
            _station_from_title("【道の駅こすげ】秋まつり", MASTER)["roadName"],
            "こすげ")
        self.assertIsNone(
            _station_from_title("和光市で秋のイベント開催", MASTER))
        self.assertIsNone(
            _station_from_title("【道の駅同名の駅】秋まつり", MASTER))

    def test_same_official_url_is_recognized_as_published(self):
        report = self.report()
        self.assertEqual(report["summary"]["officialSources"], 2)
        self.assertEqual(report["summary"]["announcementsCompared"], 2)
        self.assertEqual(
            report["summary"]["statuses"]["published_same_official_url"], 1)
        self.assertEqual(
            report["summary"]["statuses"]["unmatched_official_notice"], 1)
        self.assertEqual(report["summary"]["candidatesForManualReview"], 1)
        self.assertEqual(report["summary"]["sampleDiscoveryRate"], None)

    def test_different_url_but_near_identical_name_is_review_not_missing(self):
        item = {"title": "【道の駅庄和】わくわく体験イベント",
                "url": "https://www.kanto-michinoeki.jp/archives/90000.html"}
        report = self.report(regional={"sources": [
            {"region": "関東", "reachable": True, "candidates": [item]}]})
        self.assertEqual(
            report["summary"]["statuses"]["possible_same_event_other_url"], 1)
        self.assertEqual(report["summary"]["candidatesForManualReview"], 0)

    def test_same_pdf_url_different_event_must_still_be_reviewed(self):
        published = [{
            "prefecture": "三重県", "roadName": "飯高駅",
            "title": "【物産展】秋の催し", "startDate": "2026-10-25",
            "endDate": "2026-10-25", "url": PDF}]
        region = {"sources": [{"region": "近畿", "reachable": True,
                  "candidates": [{"title": "【体験会】秋の催し 開催",
                                  "url": PDF}]}]}
        report = self.report(regional=region, published=published)
        self.assertEqual(
            report["summary"]["statuses"]["same_official_url_title_needs_review"], 1)
        self.assertEqual(report["summary"]["candidatesForManualReview"], 1)

    def test_benchmark_only_counts_independently_reviewed_on_site_examples(self):
        ledger = {"schemaVersion": 1, "reviews": [positive()]}
        report = self.report(ledger=ledger)
        self.assertEqual(report["summary"]["sampleVerifiedOnSite"], 1)
        self.assertEqual(report["summary"]["sampleFound"], 1)
        self.assertEqual(report["summary"]["sampleDiscoveryRate"], 1.0)
        self.assertIn("全国の網羅率ではありません", render_dashboard(report))

    def test_review_venue_and_date_evidence_are_mandatory(self):
        with self.assertRaisesRegex(ValueError, "independently verified"):
            reviewed_sample({"schemaVersion": 1, "reviews": [
                positive(venueEvidence="")]}, PUBLISHED)
        with self.assertRaises(ValueError):
            reviewed_sample({"schemaVersion": 1, "reviews": [
                positive(startDate="2026-11-02", endDate="2026-10-31")]}, PUBLISHED)

    def test_same_pdf_url_and_date_do_not_prove_event_was_found(self):
        pos = positive(officialUrl=PDF, prefecture="三重県", roadName="飯高駅",
                       title="【体験会】秋の催し", startDate="2026-10-25",
                       endDate="2026-10-25")
        other = [{"prefecture": "三重県", "roadName": "飯高駅",
                  "title": "【物産展】秋の催し", "url": PDF,
                  "startDate": "2026-10-25", "endDate": "2026-10-25"}]
        result = reviewed_sample({"schemaVersion": 1, "reviews": [pos]}, other)
        self.assertEqual(result["notFound"], 1)
        self.assertEqual(result["rateWithinReviewedSample"], 0.0)

    def test_other_date_same_event_is_not_an_automatic_hit(self):
        future = positive(startDate="2026-11-03", endDate="2026-11-03")
        result = reviewed_sample({"schemaVersion": 1, "reviews": [future]}, PUBLISHED)
        self.assertEqual(result["notFound"], 1)

    def test_negative_review_does_not_enter_recall_denominator(self):
        entry = {"decision": "not_station_event", "reviewedOn": DAY,
                 "officialUrl": "https://izuminambu-rc.jp/nb_event/example",
                 "reason": "Event takes place at the city community centre"}
        result = reviewed_sample({"schemaVersion": 1, "reviews": [entry]}, PUBLISHED)
        self.assertEqual(result["reviewed"], 1)
        self.assertEqual(result["positiveOnSite"], 0)
        self.assertIsNone(result["rateWithinReviewedSample"])

    def test_review_duplicate_and_incomplete_negative_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            reviewed_sample({"schemaVersion": 1, "reviews": [positive(), positive()]},
                            PUBLISHED)
        with self.assertRaisesRegex(ValueError, "reason"):
            reviewed_sample({"schemaVersion": 1, "reviews": [{
                "decision": "not_station_event", "reviewedOn": DAY,
                "officialUrl": "https://official.example/n"}]}, PUBLISHED)


if __name__ == "__main__":
    unittest.main()

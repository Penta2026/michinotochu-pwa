"""Offline regressions for registry-driven official article reconfirmation."""
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import requests

from verified_station_engine import (
    _confirm, _rule_for, _subject, reconfirm_known_articles,
)
from road_event_quality import reconcile

TODAY = date(2026, 10, 10)
RULES = [
    {"id":"kasama","prefecture":"茨城県","roadName":"かさま",
     "allowedHosts":["m-kasama.com"],"pathPattern":r"^/topics/p-\d+/?$"},
    {"id":"hotasho","prefecture":"千葉県","roadName":"保田小学校",
     "allowedHosts":["hotasho.jp"],"pathPattern":r"^/news/.+"},
]
KASAMA = {
    "prefecture":"茨城県","roadName":"かさま",
    "title":"2026.09.23 イベント お知らせ 【イベント】10/17~18『モンブランフェア』を開催します",
    "startDate":"2026-10-17","endDate":"2026-10-18",
    "url":"https://m-kasama.com/topics/p-06506","status":"scheduled",
}
HOTASHO = {
    "prefecture":"千葉県","roadName":"保田小学校",
    "title":"保田小附属ようちえん3周年開園祭(2026.10.10~12)",
    "startDate":"2026-10-10","endDate":"2026-10-12",
    "url":"https://hotasho.jp/news/anniversary/","status":"scheduled",
}
KASAMA_HTML = """<main><article>
    <h1>【イベント】10/17～18『モンブランフェア』を開催します</h1>
    <p>道の駅かさまでモンブランフェアを開催！</p>
    </article></main>"""
HOTASHO_HTML = """<main><article><h1>保田小附属ようちえん3周年開園祭（2026.10.10～12）</h1>
    <p>日にち：2026年10月10日（土）～12日（月）</p></article></main>"""

class VerifiedArticleReconfirmationTests(unittest.TestCase):
    def test_subject_is_event_not_station_name(self):
        title = "「道の駅 奥永源寺渓流の里」開駅１１周年記念祭を開催します。"
        self.assertIn("開駅11周年記念祭", _subject(title))
        self.assertEqual(_subject(KASAMA["title"]), _subject("モンブランフェア"))

    def test_confirms_official_matching_event_and_period(self):
        self.assertEqual(_confirm(KASAMA, KASAMA_HTML), (True, "reconfirmed"))
        self.assertEqual(_confirm(HOTASHO, HOTASHO_HTML), (True, "reconfirmed"))

    def test_mismatched_dates_never_reconfirm(self):
        html = KASAMA_HTML.replace("10/17～18", "10/24～25")
        self.assertEqual(_confirm(KASAMA, html),
                         (False, "date_not_reconfirmed"))

    def test_mismatched_title_never_reconfirm(self):
        html = KASAMA_HTML.replace("モンブランフェア", "秋の収穫祭")
        self.assertEqual(_confirm(KASAMA, html),
                         (False, "title_not_found"))

    def test_missing_article_never_reconfirms(self):
        self.assertEqual(_confirm(KASAMA, "<nav><a>10/17 モンブランフェア</a></nav>"),
                         (False, "no_article_content"))

    def test_registry_matches_station_and_official_host(self):
        self.assertEqual(_rule_for(KASAMA, RULES)["id"], "kasama")
        self.assertIsNone(_rule_for(dict(KASAMA,url="https://evil.example/topics/p-06506"), RULES))
        self.assertIsNone(_rule_for(dict(KASAMA,url="http://m-kasama.com/topics/p-06506"), RULES))
        self.assertIsNone(_rule_for(dict(KASAMA,url="https://m-kasama.com.evil.example/topics/p-06506"), RULES))
        self.assertIsNone(_rule_for(dict(KASAMA,roadName="庄和"), RULES))

    def test_adds_only_previously_verified_record_without_modifying_fields(self):
        with TemporaryDirectory() as tmp:
            recovered, audit = reconfirm_known_articles(
                TODAY, [KASAMA,HOTASHO], [], rules=RULES,
                fetch=lambda url: KASAMA_HTML if "kasama" in url else HOTASHO_HTML,
                report_path=Path(tmp)/"audit.json")
            self.assertEqual(len(recovered),2)
            self.assertEqual(recovered[0],KASAMA)
            self.assertEqual(recovered[1],HOTASHO)
            self.assertEqual(audit["reconfirmed"],2)
            self.assertTrue((Path(tmp)/"audit.json").exists())
            final, quality = reconcile([KASAMA,HOTASHO], recovered, TODAY)
            self.assertEqual(len(final),2)
            self.assertEqual(quality["notReconfirmed"],[])

    def test_skips_already_collected_without_network(self):
        def fail_fetch(_):
            self.fail("Should not fetch an already-collected item")
        recovered,audit = reconfirm_known_articles(
            TODAY, [KASAMA], [KASAMA], rules=RULES,
            fetch=fail_fetch, report_path=None)
        self.assertEqual(recovered, [])
        self.assertEqual(audit["alreadyCollected"], 1)
        self.assertEqual(audit["checked"], 0)

    def test_failed_network_preserves_unconfirmed_in_quality(self):
        def timeout(_):
            raise requests.Timeout("offline")
        recovered,audit = reconfirm_known_articles(
            TODAY,[KASAMA],[],rules=RULES,fetch=timeout,report_path=None)
        self.assertEqual(recovered,[])
        self.assertEqual(audit["failed"],1)
        final,quality = reconcile([KASAMA],recovered,TODAY)
        self.assertEqual(len(final),1)
        self.assertEqual(len(quality["notReconfirmed"]),1)

    def test_recent_fukui_miyazaki_reconfirm_registry_urls(self):
        import json
        from verified_station_engine import RULES as REGISTERED
        rules=json.loads(REGISTERED.read_text(encoding="utf-8"))["sources"]
        fukui={"prefecture":"福井県","roadName":"南えちぜん山海里",
               "url":"https://kineno-nanjo.com/info/news/post-5318/"}
        miyazaki={"prefecture":"宮崎県","roadName":"都城NiQLL",
                  "url":"https://coconiqll.co.jp/%e3%80%90niqlls%e3%82%ad%e3%83%83%e3%83%81%e3%83%b3%e3%80%9111%e6%9c%88%e3%80%80%e7%a7%8b%e3%81%ae%e8%95%8e%e9%ba%a6%e6%89%93%e3%81%a1%e4%bd%93%e9%a8%93/"}
        self.assertEqual(_rule_for(fukui,rules)["id"],"fukui_sankairi")
        self.assertEqual(_rule_for(miyazaki,rules)["id"],"miyazaki_niqll")
        self.assertIsNone(_rule_for({**miyazaki,"url":"https://evil.example/event/"},rules))

    def test_yamaguchi_abu_verification_rule_matches_existing_url_only(self):
        import json
        from verified_station_engine import RULES as REGISTERED
        rules=json.loads(REGISTERED.read_text(encoding="utf-8"))["sources"]
        rec={"prefecture":"山口県","roadName":"阿武町",
             "url":"https://www.abucreation.com/topics/"
                   "%e4%bb%a4%e5%92%8c6%e5%b9%b410%e6%9c%8813%e6%97%a5"
                   "%ef%bc%88%e6%97%a5%ef%bc%89%e7%ac%ac30%e5%9b%9e%e6"
                   "%a3%ae%e9%87%8c%e6%b5%b7%e3%81%ae%e5%b8%82%e3%82%92"
                   "%e9%96%8b%e5%82%ac%e3%81%97%e3%81%be%e3%81%99/"}
        self.assertEqual(_rule_for(rec,rules)["id"],"yamaguchi_abu")
        self.assertIsNone(_rule_for({**rec,"roadName":"あいお"},rules))
        self.assertIsNone(_rule_for({**rec,"url":"https://evil.example/topics/post/"},rules))
        self.assertIsNone(_rule_for({**rec,"url":"https://www.abucreation.com/other"},rules))

    def test_unmatched_rule_never_creates_event(self):
        fake=dict(KASAMA,prefecture="東京都")
        recovered,audit=reconfirm_known_articles(
            TODAY,[fake],[],rules=RULES,
            fetch=lambda url:KASAMA_HTML,report_path=None)
        self.assertEqual(recovered,[])
        self.assertEqual(audit["outsideRegistry"],1)

    def test_repeated_extraction_does_not_create_duplicate(self):
        recovered,audit=reconfirm_known_articles(
            TODAY,[KASAMA,KASAMA],[],rules=RULES,
            fetch=lambda url:KASAMA_HTML,report_path=None)
        self.assertEqual(len(recovered),1)
        self.assertEqual(audit["reconfirmed"],1)

if __name__ == "__main__":
    unittest.main()

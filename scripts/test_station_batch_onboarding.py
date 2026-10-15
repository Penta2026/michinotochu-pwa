"""Validate batch station-source onboarding against the all-station registry.

This is a safety gate, not evidence that every feed yields events.
"""
import json
import unittest
from pathlib import Path
from station_discovery_engine import _validate_sources

ROOT=Path(__file__).resolve().parents[1]

class BatchStationOnboardingTests(unittest.TestCase):
    def test_every_source_belongs_to_known_station(self):
        registry=json.loads((ROOT/"data/station_coverage_registry.json").read_text(encoding="utf-8"))
        rules=json.loads((ROOT/"data/station_event_discovery_sources.json").read_text(encoding="utf-8"))
        self.assertEqual(len(registry["stations"]),1234)
        names={(s["prefecture"],s["roadName"]) for s in registry["stations"]}
        _validate_sources(rules["sources"])
        for source in rules["sources"]:
            with self.subTest(id=source["id"]):
                self.assertIn((source["prefecture"],source["roadName"]),names)

    def test_new_hiroshima_feeds_are_separate(self):
        rules=json.loads((ROOT/"data/station_event_discovery_sources.json").read_text(encoding="utf-8"))
        selected=[s for s in rules["sources"] if s["id"] in ("hiroshima_takano","hiroshima_shinmei")]
        self.assertEqual(len(selected),2)
        self.assertEqual({s["roadName"] for s in selected},{"たかの","みはら神明の里"})
        self.assertTrue(all(s["listingUrl"].startswith("https://") for s in selected))

if __name__=="__main__": unittest.main()

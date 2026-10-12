"""Prepare a conservative, deterministic review queue for station website candidates.

This stage does NOT fetch external sites, verify ownership, or publish events.
It translates national-directory links into a per-station review backlog.
"""
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "station_official_directory_candidates.json"
OUTPUT = ROOT / "data" / "station_website_review_queue.json"

def classify(url):
    try:
        p = urlsplit(url)
        host = (p.hostname or "").lower().strip(".")
        if p.scheme not in ("http", "https") or not host or p.username or p.password or p.port:
            return "invalid"
        if host in ("localhost", "127.0.0.1", "0.0.0.0") or host.endswith((".local", ".internal")):
            return "invalid"
        if host == "www.hokkaido-michinoeki.jp" or host == "hokkaido-michinoeki.jp":
            return "regional_directory"
        if host.endswith(".lg.jp") or ".city." in host or ".town." in host or ".vill." in host:
            return "municipal_information"
        return "station_or_partner_site_unverified"
    except ValueError:
        return "invalid"

def build_queue(directory):
    stations = []
    codes = set()
    for item in directory.get("stations", []):
        code = item["id"]
        if code in codes:
            raise ValueError("Duplicate station identity in official directory")
        codes.add(code)
        rows = []
        for url in sorted(set(item.get("officialWebsiteCandidateUrlsUnverified", []))):
            category = classify(url)
            rows.append({"url": url, "kind": category, "ownershipVerified": False,
                         "eventListingVerified": False,
                         "reviewStatus": "blocked_invalid_url" if category == "invalid" else "awaiting_review"})
        priority = {"station_or_partner_site_unverified": 0, "municipal_information": 1,
                    "regional_directory": 2, "invalid": 3}
        rows.sort(key=lambda r: (priority[r["kind"]], r["url"]))
        stations.append({"id": code, "prefecture": item["prefecture"],
                         "roadName": item["roadName"],
                         "directoryDetailUrl": item.get("directoryDetailUrl", ""),
                         "candidates": rows,
                         "siteVerificationState": "awaiting_review" if rows else "no_candidate_found",
                         "eventCoverageState": "not_assessed"})
    stations.sort(key=lambda x: x["id"])
    tally = Counter(c["kind"] for s in stations for c in s["candidates"])
    return {"schemaVersion": 1, "sourceDirectoryLastChecked": directory.get("lastChecked", ""),
            "stationsWithCandidates": sum(bool(s["candidates"]) for s in stations),
            "stationsReviewed": 0, "eventListingsVerified": 0,
            "candidateKinds": dict(sorted(tally.items())), "stations": stations}

def main():
    src = json.loads(SOURCE.read_text(encoding="utf-8"))
    result = build_queue(src)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != text:
        OUTPUT.write_text(text, encoding="utf-8")
    print("Station URL review queue: {} stations with candidates / 0 verified; no external requests".format(result["stationsWithCandidates"]))

if __name__ == "__main__":
    main()

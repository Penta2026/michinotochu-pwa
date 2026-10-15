"""Inspect up to 36 candidate homepages per day; never auto-publish sources."""
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup

DATA = Path(__file__).resolve().parents[1] / "data"
OUTPUT = DATA / "station_website_batch_audit.json"
MAX_SITES = 36
TERMS = ("イベント", "催し", "行事", "お知らせ", "祭", "event", "news")
AGENT = "MichinotochuStationSiteReview/1.0"


def eligible(queue, previous):
    seen = {(r["stationId"], r["url"]) for r in previous.get("results", [])}
    for station in queue["stations"]:
        if station.get("directoryInspectionState") != "checked":
            continue
        for hint in station.get("candidates", []):
            p = urlparse(hint["url"])
            if (hint.get("reviewStatus") == "awaiting_review"
                    and hint.get("kind") == "station_or_partner_site_unverified"
                    and p.scheme == "https" and p.hostname and not p.username
                    and not p.password and not p.port
                    and (station["id"], hint["url"]) not in seen):
                yield station, hint["url"]


def analyze(station, url, response):
    if response.status_code != 200 or len(response.content) > 500000:
        return {"status": "http_or_size_rejected", "eventLinkHints": []}
    soup = BeautifulSoup(response.content, "html.parser")
    name = station["roadName"].replace("　", " ").strip()
    identity = name in soup.get_text(" ", strip=True)
    links = []
    for a in soup.select("a[href]"):
        if not any(term in a.get_text(" ", strip=True).lower() for term in TERMS):
            continue
        link = urljoin(url, a["href"])
        if urlparse(link).scheme == "https" and urlparse(link).hostname == urlparse(url).hostname:
            if link not in links:
                links.append(link)
    return {"status": "identity_mentioned_unverified" if identity else "identity_not_found",
            "stationNameMentioned": identity, "eventLinkHints": links[:8],
            "ownershipVerified": False, "eventListingVerified": False}


def run(queue, previous, fetch, allowed, limit=MAX_SITES, priority=None):
    if not 1 <= limit <= MAX_SITES:
        raise ValueError("Too many external station requests")
    candidates = list(eligible(queue, previous))
    if priority is not None:
        # Prioritize provinces without published events; all entries are
        # still taken exclusively from the same validated review queue.
        ranked = {(p["stationId"], p["url"]): i
                  for i, p in enumerate(priority)}
        candidates.sort(key=lambda item: (
            ranked.get((item[0]["id"], item[1]), len(ranked)),
            item[0]["id"], item[1]))
    additions = []
    for station, url in candidates[:limit]:
        record = {"stationId": station["id"], "prefecture": station["prefecture"],
                  "roadName": station["roadName"], "url": url}
        if not allowed(url):
            result = {"status": "robots_blocked", "eventLinkHints": []}
        else:
            try:
                result = analyze(station, url, fetch(url))
            except requests.RequestException as error:
                result = {"status": "fetch_failed", "errorType": type(error).__name__,
                          "eventLinkHints": []}
        additions.append({**record, **result})
    return {"schemaVersion": 1, "checkedAt": datetime.now(timezone.utc).isoformat(),
            "maxSitesPerRun": limit, "newlyChecked": len(additions),
            "results": previous.get("results", []) + additions,
            "nextBatchEligible": len(candidates) - len(additions),
            "limitations": "Station mentions and candidate links are not verified ownership, event dates, or publishable events."}


def main():
    queue = json.loads((DATA / "station_website_review_queue.json").read_text(encoding="utf-8"))
    previous = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    priority_file = DATA / "station_website_priority.json"
    priority = json.loads(priority_file.read_text(encoding="utf-8")).get(
        "reviewPriority", []) if priority_file.exists() else None
    session = requests.Session()
    session.headers.update({"User-Agent": AGENT})
    robots = {}
    def allowed(url):
        p = urlparse(url)
        host = p.scheme + "://" + p.netloc
        if host not in robots:
            try:
                r = session.get(host + "/robots.txt", timeout=8, allow_redirects=False)
                parser = RobotFileParser()
                parser.parse(r.text.splitlines())
                robots[host] = parser if r.status_code == 200 else None
            except requests.RequestException:
                robots[host] = None
        return bool(robots[host] and robots[host].can_fetch(AGENT, url))
    result = run(queue, previous,
                 lambda url: session.get(url, timeout=12, allow_redirects=False),
                 allowed, priority=priority)
    data = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != data:
        OUTPUT.write_text(data, encoding="utf-8")
    print("Station website review: {} newly inspected, {} total, {} next eligible".format(
        result["newlyChecked"], len(result["results"]), result["nextBatchEligible"]))


if __name__ == "__main__":
    main()

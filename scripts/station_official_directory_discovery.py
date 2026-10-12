"""Conservative pilot: discover official-link HINTS from the national Michi-no-Eki directory.

Fetch ONLY publicly listed directory pages (never follow external candidate links).
Strict prefecture+station-name match against app master. Keep all discovered links
UNVERIFIED. Robots policy checked on every run. No event is published here.
"""
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from station_coverage_registry import DATA, read_app_stations, station_key

HOST = "www.michi-no-eki.jp"
BASE = "https://" + HOST
LIST_BASE = BASE + "/stations/search/all/all/all"  # all prefectures, paginated
OUTPUT = DATA / "station_official_directory_candidates.json"
JST = timezone(timedelta(hours=9))
AGENT = "MichinotochuStationLinkAudit/1.0 (bounded public-directory lookups)"
MAX_DETAIL_PAGES = 24
MAX_BYTES = 750_000


def same_directory_url(url, *, detail=False):
    p = urlparse(url)
    if p.scheme != "https" or p.hostname != HOST or p.username or p.password or p.port:
        return False
    return bool(re.fullmatch(r"/stations/views/[0-9]+", p.path) if detail
                else re.fullmatch(r"/stations/search/(?:[0-9]+|all)/all/all", p.path))


def listing_matches(html, roads):
    """Reject ambiguous/partial station names; do not guess a station ID."""
    lookup = {}
    for r in roads:
        key = station_key(r["prefecture"], r["name"])
        lookup.setdefault(key, []).append(r)
    found = {}
    for a in BeautifulSoup(html, "html.parser").select("a[href]"):
        url = urljoin(BASE, a.get("href", ""))
        if not same_directory_url(url, detail=True):
            continue
        label = " ".join(a.stripped_strings)
        for pref in sorted({r["prefecture"] for r in roads}, key=len, reverse=True):
            if pref not in label:
                continue
            name = label.split(pref, 1)[0].strip()
            candidates = lookup.get(station_key(pref, name), [])
            if len(candidates) == 1:
                record = candidates[0]
                # One directory detail URL may not claim two stations.
                found.setdefault(url, {"id": record["id"],
                                       "prefecture": pref, "roadName": record["name"],
                                       "directoryDetailUrl": url})
            break
    ids = [x["id"] for x in found.values()]
    if len(ids) != len(set(ids)):
        raise ValueError("Directory listing contains duplicate app station identity")
    return list(found.values())


def detail_hints(html, listing):
    """Parse labelled HomePage fields only, NOT any arbitrary outbound anchor."""
    soup = BeautifulSoup(html, "html.parser")
    name = station_key(listing["prefecture"], listing["roadName"])[1]
    headings = [station_key(listing["prefecture"],
                            re.sub(r"^道の駅[「『]?(.*?)[」』]?$", r"\1",
                                   h.get_text(" ", strip=True)))[1]
                for h in soup.select("h1,h2,h3")]
    if name not in headings:
        return None  # website or directory layout changed, do not mismatch
    candidates = set()
    for label in soup.find_all(string=lambda t: t and t.strip() in
                               ("ホームページ", "ホームページ2")):
        parent = label.parent
        siblings = [parent, parent.find_next_sibling()]
        if parent.parent and parent.parent.name in ("tr", "dl"):
            siblings.append(parent.parent)
        for sibling in siblings:
            if sibling is None:
                continue
            for a in sibling.select("a[href]"):
                href = a.get("href", "").strip()
                u = urljoin(BASE, href)
                p = urlparse(u)
                if p.scheme not in ("https", "http") or not p.hostname or p.username or p.password:
                    continue
                if p.hostname == HOST:
                    continue
                candidates.add(u)
    return sorted(candidates)


def robots_policy(fetch):
    """On uncertainty, abort; avoid intrusive or unauthorized bulk access."""
    url = BASE + "/robots.txt"
    status, body = fetch(url, robots=True)
    if status == 404:
        return lambda url: True
    if status != 200:
        raise RuntimeError("robots.txt unavailable, HTTP " + str(status))
    parser = RobotFileParser()
    parser.parse(body.splitlines())
    return lambda url: parser.can_fetch(AGENT, url)


def crawl_once(fetch, *, robots_allowed, old=None, max_details=MAX_DETAIL_PAGES,
               scanned_on=None, pause=None):
    """One resumable national listing page; limit station details per daily run."""
    old = old or {}
    if old.get("listingTraversalCompleted"):
        return {**old, "lastRun": {"listCount": 0, "inspected": 0,
                                   "matched": 0, "errors": 0}}
    old_rows = {x["id"]: x for x in old.get("stations", [])}
    cursor = old.get("cursor", {"page": 0, "offset": 0})
    page, offset = int(cursor["page"]), int(cursor["offset"])
    if page < 0 or offset < 0 or not 1 <= max_details <= 24:
        raise ValueError("Invalid bounded crawl settings")
    scanned_on = scanned_on or datetime.now(JST).date().isoformat()
    listing_url = LIST_BASE + ("?page=" + str(page) if page else "")
    if not robots_allowed(listing_url):
        raise RuntimeError("robots policy disallows directory listing")
    code, html = fetch(listing_url)
    if code != 200:
        raise RuntimeError("directory listing HTTP " + str(code))
    roads = read_app_stations((DATA / "app_data.js").read_text(encoding="utf-8"))
    matches = listing_matches(html, roads)
    if not matches:
        # Log only page structure and a few short link labels (not page text),
        # to diagnose a changed directory template without skipping stations.
        candidate_links = [
            (" ".join(a.stripped_strings)[:100], a.get("href", "")[:140])
            for a in BeautifulSoup(html, "html.parser").select("a[href]")
            if same_directory_url(urljoin(BASE, a.get("href", "")), detail=True)
        ]
        raise RuntimeError(
            "directory listing has no exact master matches; page={} "
            "detail_links={} examples={}".format(
                page, len(candidate_links), candidate_links[:5]))
    # Offsets should never exceed the page just fetched: fail rather than
    # claiming that the whole national directory has been checked.
    if offset >= len(matches):
        raise RuntimeError("Cursor beyond official listing; review source changes")
    inspected = 0
    matched = 0
    errors = 0
    for item in matches[offset:offset + max_details]:
        url = item["directoryDetailUrl"]
        status, hints = "not_checked", []
        if not robots_allowed(url):
            status = "robots_disallowed"
            errors += 1
        else:
            if pause:
                pause(1.5)
            code, detail = fetch(url)
            inspected += 1
            if code != 200:
                status = "http_" + str(code)
                errors += 1
            else:
                result = detail_hints(detail, item)
                if result is None:
                    status = "station_identity_not_confirmed"
                    errors += 1
                else:
                    status, hints = "directory_identity_checked", result
                    matched += 1
        old_rows[item["id"]] = {
            **item, "lastDirectoryChecked": scanned_on,
            "directoryCheckStatus": status,
            "officialWebsiteCandidateUrlsUnverified": hints,
            "evidence": "national_station_association_directory_detail_only",
            "officialSiteOwnershipVerified": False,
        }
    end = min(len(matches), offset + max_details)
    # The directory has 1,234 entries split across paginated national results.
    # Stop only after a real last page, not after exhausting one prefecture.
    soup = BeautifulSoup(html, "html.parser")
    has_next = any(
        same_directory_url(urljoin(BASE, a.get("href", ""))) and
        urlparse(urljoin(BASE, a.get("href", ""))).path == urlparse(LIST_BASE).path and
        parse_qs(urlparse(urljoin(BASE, a.get("href", ""))).query).get("page")
            == [str(page + 1)]
        for a in soup.select("a[href]")
    )
    completed = end == len(matches) and not has_next
    cursor = ({"page": page + 1, "offset": 0} if end == len(matches) and has_next
              else {"page": page, "offset": end})
    return {"schemaVersion": 1, "source": BASE + "/search",
            "lastChecked": scanned_on, "cursor": cursor,
            "listingTraversalCompleted": completed,
            "stations": sorted(old_rows.values(), key=lambda x: x["id"]),
            "lastRun": {"listCount": len(matches), "inspected": inspected,
                        "matched": matched, "errors": errors}}


def crawl_batch(fetch, *, robots_allowed, old=None, max_details=MAX_DETAIL_PAGES,
                scanned_on=None, pause=None):
    """Spend today's small request budget across page boundaries safely."""
    if not 1 <= max_details <= 24:
        raise ValueError("Unreasonable daily directory request budget")
    current = old or {}
    remaining = max_details
    totals = {"listCount": 0, "inspected": 0, "matched": 0,
              "errors": 0, "examined": 0, "listingPagesVisited": 0}
    for _ in range(4):  # normally at most two, defensive cap
        if not remaining or current.get("listingTraversalCompleted"):
            break
        previous = current.get("cursor", {"page": 0, "offset": 0})
        result = crawl_once(fetch, robots_allowed=robots_allowed, old=current,
                            max_details=remaining, scanned_on=scanned_on,
                            pause=pause)
        run = result["lastRun"]
        # Checked rows includes robots-blocked rows with no HTTP GET.
        examined = (result["cursor"]["offset"] - previous["offset"]
                    if result["cursor"]["page"] == previous["page"] else
                    run["listCount"] - previous["offset"])
        if examined <= 0 or examined > remaining:
            raise RuntimeError("Directory cursor failed to make safe progress")
        for field in ("inspected", "matched", "errors"):
            totals[field] += run[field]
        totals["examined"] += examined
        totals["listingPagesVisited"] += 1
        totals["listCount"] = run["listCount"]
        remaining -= examined
        current = result
        if (current.get("listingTraversalCompleted")
                or result["cursor"]["page"] == previous["page"]):
            break
    if not current:
        raise RuntimeError("Directory batch produced no output")
    return {**current, "lastRun": totals}


def network_fetch(session):
    def fetch(url, robots=False):
        if not (url == BASE + "/robots.txt" if robots else (same_directory_url(url) or same_directory_url(url, detail=True))):
            raise ValueError("Refusing off-directory request")
        response = session.get(url, timeout=12, allow_redirects=False)
        if len(response.content) > MAX_BYTES:
            raise ValueError("Oversized directory response")
        return response.status_code, response.text
    return fetch


def main():
    old = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    with requests.Session() as session:
        session.headers.update({"User-Agent": AGENT, "Accept": "text/html"})
        fetch = network_fetch(session)
        allowed = robots_policy(fetch)
        result = crawl_batch(fetch, robots_allowed=allowed, old=old, pause=time.sleep)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != text:
        OUTPUT.write_text(text, encoding="utf-8")
    print("全国道の駅公式名簿: 追加詳細検査 {} / 駅名一致 {} / エラー {} / 候補URL登録済駅 {} / 次の巡回 {}".format(
        result["lastRun"]["inspected"], result["lastRun"]["matched"],
        result["lastRun"]["errors"], sum(bool(x["officialWebsiteCandidateUrlsUnverified"])
                                        for x in result["stations"]), result["cursor"]))


if __name__ == "__main__":
    main()

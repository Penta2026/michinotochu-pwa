"""Strict, bounded national station event probe from *unverified* website hints.

A directory link is NOT automatically official. Only publish an event when:
  - the website was listed in the national directory and named the exact station;
  - the event page is on the same HTTPS host and robots permits it;
  - one event-specific article explicitly says its FULL YEAR date and on-site venue.
This supplements vetted adapters. All failures stay in the audit, never as events.
"""
import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from station_coverage_registry import station_key
from station_discovery_engine import _article_record, EVENT_WORDS, BLOCK

DATA = Path(__file__).resolve().parents[1] / "data"
OUT = DATA / "station_national_event_candidates.json"
AUDIT = DATA / "station_national_event_probe_audit.json"
AGENT = "MichinotochuNationwideEventProbe/1.0"
MAX_STATIONS_PER_DAY = 60
MAX_ARTICLES_PER_STATION = 3
JST = timezone(timedelta(hours=9))
DATE = re.compile(r"(?<![0-9])20[0-9]{2}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?")
DATE_LABEL = re.compile(r"開催日|開催日時|開催期間|イベント日時|実施日|日時|日程")


def safe_same_host(url, home):
    try:
        p, base = urlsplit(url), urlsplit(home)
        if (p.scheme != "https" or p.hostname != base.hostname
                or p.username or p.password or p.port is not None
                or not p.hostname or not p.path.startswith("/")
                or "/../" in p.path or "/./" in p.path):
            return False
    except ValueError:
        return False
    return True


def eligible_targets(queue, website_audit, sources, history, today, limit=MAX_STATIONS_PER_DAY):
    if not 1 <= limit <= MAX_STATIONS_PER_DAY:
        raise ValueError("Station event probe budget exceeded")
    stations = {s["id"]: s for s in queue["stations"]}
    if len(stations) != len(queue["stations"]):
        raise ValueError("Duplicate station IDs")
    configured = {station_key(x["prefecture"], x["roadName"])
                  for x in sources.get("sources", []) if x.get("enabled", True)}
    latest = {}
    for record in website_audit.get("results", []):
        key = (record.get("stationId"), record.get("url"))
        latest[key] = record
    prior = {x["stationId"]: x for x in history.get("stations", [])
             if x.get("stationId")}
    choices = []
    for (station_id, home), item in latest.items():
        station = stations.get(station_id)
        if not station or station.get("directoryInspectionState") != "checked":
            continue
        if station_key(station["prefecture"], station["roadName"]) in configured:
            continue
        if (item.get("status") != "identity_mentioned_unverified"
                or not item.get("stationNameMentioned") or len(station["roadName"]) < 3):
            continue
        if home not in {hint.get("url") for hint in station.get("candidates", [])
                        if hint.get("kind") == "station_or_partner_site_unverified"}:
            continue
        urls = list(dict.fromkeys(
            u for u in item.get("eventLinkHints", []) if safe_same_host(u, home)))
        if not urls:
            continue
        old = prior.get(station_id, {})
        # New candidates first; after nationwide first pass, revisit sources
        # at least every 7 days for newly published announcements.
        scanned = old.get("lastChecked", "")
        try:
            age = (today - date.fromisoformat(scanned)).days if scanned else 999
        except ValueError:
            age = 999
        if age < 7:
            continue
        choices.append({
            "stationId": station_id, "prefecture": station["prefecture"],
            "roadName": station["roadName"], "websiteUrl": home,
            "articleHints": urls[:8], "lastChecked": scanned,
            "newStation": not scanned,
        })
    # New stations must not starve while the first 1,234-station scan advances.
    choices.sort(key=lambda x: (
        not x["newStation"], x["lastChecked"],
        x["stationId"], x["websiteUrl"]))
    selected, seen = [], set()
    for x in choices:
        if x["stationId"] in seen:
            continue
        selected.append(x)
        seen.add(x["stationId"])
        if len(selected) >= limit:
            break
    return selected, len({x["stationId"] for x in choices})


def _text_lines(node):
    return [" ".join(unicodedata.normalize("NFKC", s).split())
            for s in node.get_text("\n", strip=True).splitlines() if s.strip()]


def parse_strict_event(html, station, url, today):
    """No posting-date inference, calendar/date mixing or generic footer venue."""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main") or soup.select_one("body")
    articles = main.select("article") if main else []
    if len(articles) > 1:
        return None, "multiple_articles"
    container = articles[0] if articles else main
    if container is None:
        return None, "no_article"
    # A generic news listing with many event headlines is NOT one event.
    headings = [h.get_text(" ", strip=True) for h in container.select("h1,h2,h3")]
    named = [h for h in headings if any(w in h for w in EVENT_WORDS)
             and not any(b in h for b in BLOCK)]
    if len(named) != 1:
        return None, "no_unique_event_headline"
    lines = _text_lines(container)
    # Require a YEAR in the event's own dated sentence, not a post date,
    # registration deadline, footer date, or today's inferred year.
    event_date_lines = [
        x for x in lines
        if DATE.search(x) and DATE_LABEL.search(x)
        and not re.search(r"投稿日|更新日|公開日|掲載日|募集|申込|受付|締切|応募", x)
    ]
    if not event_date_lines:
        return None, "no_explicit_year_event_date"
    name = " ".join(unicodedata.normalize("NFKC", station["roadName"]).split())
    # A short/common station name requires the explicit 道の駅 prefix.
    station_venue = (r"道の駅\s*" if len(name) < 6 else r"(?:道の駅\s*)?") + re.escape(name)
    venue_pattern = (r"(?:会場|開催場所|開催会場|開催地|場所)\s*[:：]?\s*"
                     + station_venue)
    body = " ".join(lines)
    if not re.search(venue_pattern, body):
        return None, "no_explicit_on_site_venue"
    spec = {
        "roadName": station["roadName"], "prefecture": station["prefecture"],
        "articleSelector": "article, main, body",
        "titleSelectors": ["article h1", "main h1", "article h2", "main h2", "h1", "h2", "h3"],
        "requiredVenueTokens": ["道の駅" + name],
        "venueProofPattern": venue_pattern,
        "requireVenueLabel": True,
        "allowedEventWords": list(EVENT_WORDS),
        "splitArticleTextLines": True,
    }
    event, why = _article_record(spec, soup, named[0], today, url)
    if event is None:
        return None, why
    if not any(
        date.fromisoformat(event["startDate"]) == date(
            *[int(x) for x in m.groups()])
        for line in event_date_lines
        for m in re.finditer(r"(?<![0-9])(20[0-9]{2})[年./-]([0-9]{1,2})[月./-]([0-9]{1,2})", line)
        if _valid_date_match(m)
    ):
        return None, "date_not_from_explicit_event_line"
    if date.fromisoformat(event["startDate"]) > today + timedelta(days=366):
        return None, "event_too_far_in_future"
    return event, ""


def _valid_date_match(match):
    try:
        date(*(int(x) for x in match.groups()))
        return True
    except ValueError:
        return False


def listing_event_links(html, base):
    """Conservatively descend one level for generic /news/ or /events/ pages."""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("main") or soup.select_one("body")
    if not container:
        return []
    found = []
    for a in container.select("a[href]"):
        text = " ".join(a.get_text(" ", strip=True).split())
        if (len(text) < 7 or not any(w in text for w in EVENT_WORDS)
                or any(x in text for x in BLOCK)):
            continue
        url = urljoin(base, a.get("href", ""))
        if not safe_same_host(url, base) or url == base or url in found:
            continue
        found.append(url)
    # Recent explicit year in URL preferred as a hint, never date proof.
    found.sort(key=lambda x: ("2026" not in x and "2027" not in x, x))
    return found[:6]


def collect(targets, old, today, fetch, allowed):
    previous = {
        (e.get("url"), e.get("roadName"), e.get("startDate")): e
        for e in old.get("events", []) if e.get("endDate", "") >= today.isoformat()
    }
    checked = {x["stationId"]: x for x in old.get("stations", [])
               if x.get("stationId")}
    audit = []
    for station in targets:
        home = station["websiteUrl"]
        candidate_links = station["articleHints"][:4]
        details = []
        inspected = set()
        accepted = 0
        errors = {}
        for url in candidate_links:
            if len(inspected) >= MAX_ARTICLES_PER_STATION:
                break
            if not safe_same_host(url, home) or url in inspected:
                continue
            inspected.add(url)
            if not allowed(url):
                errors["robots_blocked"] = errors.get("robots_blocked", 0) + 1
                continue
            try:
                page = fetch(url)
            except requests.RequestException:
                errors["fetch_failed"] = errors.get("fetch_failed", 0) + 1
                continue
            event, why = parse_strict_event(page, station, url, today)
            if event:
                previous[(event["url"], event["roadName"], event["startDate"])] = event
                accepted += 1
                continue
            errors[why] = errors.get(why, 0) + 1
            # Only use spare budget to descend ONE verified same-host listing.
            if (why in ("multiple_articles", "no_unique_event_headline")
                    and re.search(r"/(?:news|events?|topics|information)/?$", urlsplit(url).path)):
                details.extend(listing_event_links(page, url))
            for candidate in details:
                if len(inspected) >= MAX_ARTICLES_PER_STATION:
                    break
                if candidate in inspected or not safe_same_host(candidate, home):
                    continue
                inspected.add(candidate)
                if not allowed(candidate):
                    errors["robots_blocked"] = errors.get("robots_blocked", 0) + 1
                    continue
                try:
                    inner = fetch(candidate)
                except requests.RequestException:
                    errors["fetch_failed"] = errors.get("fetch_failed", 0) + 1
                    continue
                parsed, reason = parse_strict_event(inner, station, candidate, today)
                if parsed:
                    previous[(parsed["url"], parsed["roadName"], parsed["startDate"])] = parsed
                    accepted += 1
                else:
                    errors[reason] = errors.get(reason, 0) + 1
        checked[station["stationId"]] = {
            "stationId": station["stationId"], "roadName": station["roadName"],
            "lastChecked": today.isoformat(), "articlePagesChecked": len(inspected),
            "accepted": accepted, "rejectedReasons": errors,
        }
        audit.append(checked[station["stationId"]])
    events = sorted(previous.values(), key=lambda x: (x["startDate"],x["prefecture"],x["roadName"],x["url"]))
    return {"schemaVersion": 1, "updatedAt": today.isoformat(), "events": events,
            "limitations": "Only full-year, station-venue-labelled individual notices; candidates were found via unverified station site hints."}, {
            "schemaVersion": 1, "checkedAt": today.isoformat(),
            "stationUrlsInspected": len(targets), "newlyAccepted": sum(x["accepted"] for x in audit),
            "stations": sorted(checked.values(), key=lambda x: x["stationId"]),
            "todayDetails": audit,
            "publicationGate": "explicit event full-year date and labelled on-station venue",
        }


def network():
    session = requests.Session()
    session.headers.update({"User-Agent": AGENT})
    robots = {}
    def allowed(url):
        p = urlsplit(url)
        base = p.scheme + "://" + p.netloc
        if base not in robots:
            try:
                r = session.get(base + "/robots.txt", timeout=5, allow_redirects=False)
                if r.status_code != 200:
                    robots[base] = None
                else:
                    parser = RobotFileParser()
                    parser.parse(r.text.splitlines())
                    robots[base] = parser
            except requests.RequestException:
                robots[base] = None
        return bool(robots[base] and robots[base].can_fetch(AGENT, url))
    def fetch(url):
        r = session.get(url, timeout=9, allow_redirects=False)
        if r.status_code != 200 or len(r.content) > 600000:
            raise requests.RequestException(f"HTTP {r.status_code} / oversized")
        r.encoding = r.apparent_encoding if r.encoding in (None, "ISO-8859-1") else r.encoding
        return r.text
    return fetch, allowed


def main():
    today = datetime.now(JST).date()
    def read(name):
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    queue = read("station_website_review_queue.json")
    website_audit = read("station_website_batch_audit.json")
    sources = read("station_event_discovery_sources.json")
    old = read("station_national_event_candidates.json") if OUT.exists() else {}
    audit = read("station_national_event_probe_audit.json") if AUDIT.exists() else {}
    targets, available = eligible_targets(queue, website_audit, sources, audit, today)
    fetch, allowed = network()
    result, state = collect(targets, {**old, "stations": audit.get("stations", [])}, today, fetch, allowed)
    state["eligibleStationSitesBeforeBudget"] = available
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"National strict event probe: {len(targets)} station sites, "
          f"{state['newlyAccepted']} confirmed event notices, "
          f"{len(result['events'])} staged valid future events; "
          f"{available} sites eligible, unverified hints never auto-promoted.")


if __name__ == "__main__":
    main()

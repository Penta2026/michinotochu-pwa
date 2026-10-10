"""Hokuriku official event-calendar collector: station + explicit date range."""
import re
import json
from pathlib import Path
from datetime import date, timedelta
from urllib.parse import urljoin, urlparse, parse_qs
import requests
from bs4 import BeautifulSoup

BASE = "https://www.hokuriku-michinoeki.jp"
CALENDAR = BASE + "/contents/event/"
STATIONS = {"親不知ピアパーク": "新潟県", "うみてらす名立": "新潟県",
            "氷見": "富山県", "めぐみ白山": "石川県",
            "しらやまさん": "石川県"}
DATES = r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日"
EVENT_ENTRY = re.compile(r"(?P<station>" + "|".join(map(re.escape, sorted(STATIONS,key=len,reverse=True))) +
    r")\s*" + DATES + r"\s*" + DATES + r"(?P<title>.{4,140})")
HEADERS = {"User-Agent": "MichinotochuRoadEventBot/1.5 (Hokuriku official events)"}

def extract_hokuriku(text, today, source):
    """Parse individual event cards, never infer dates from page-level calendar."""
    normalized = " ".join(text.split())
    match = EVENT_ENTRY.search(normalized)
    if not match:
        return None
    station = match.group("station")
    d = match.groups()[1:7]
    try:
        first = date(*map(int, d[:3]))
        last = date(*map(int, d[3:]))
    except ValueError:
        return None
    if first > last or last < today or (last-first).days > 366:
        return None
    title = match.group("title").strip(" ・　")
    # Exclude calendar boilerplate and records without a recognisable event.
    if not title or "登録されたイベントはありません" in title:
        return None
    return {"roadName": station, "prefecture": STATIONS[station], "title": title,
            "startDate": first.isoformat(), "endDate": last.isoformat(),
            "publishedAt": "", "url": source, "status": "scheduled"}

def decode_official_response(response):
    """This site can omit HTTP charset, causing requests to treat UTF-8 as Latin-1."""
    try:
        return response.content.decode("utf-8")
    except UnicodeDecodeError:
        return response.content.decode(response.apparent_encoding or "utf-8", errors="replace")


def extract_hokuriku_cards(soup, today, page_url):
    """Read event-specific links and their surrounding card, not only link text.

    On the official calendar, station name and two dates can be sibling
    elements beside the article link. A full-page scan would mix events.
    """
    records = {}
    diagnostics = {"articleLinks": 0, "matchedCards": 0, "unmatchedArticleLinks": 0}
    for anchor in soup.select("a[href]"):
        href = urljoin(page_url, anchor.get("href", ""))
        parsed = urlparse(href)
        if parsed.hostname not in ("www.hokuriku-michinoeki.jp", "hokuriku-michinoeki.jp"):
            continue
        article_link = parsed.path.rstrip("/") == "/contents/event" and bool(parse_qs(parsed.query).get("article"))
        # Calendar cards sometimes link a different official detail URL.
        link_text = anchor.get_text(" ", strip=True)
        views = [anchor]
        parent = anchor.parent
        for _ in range(4):
            if parent is None or parent.name in ("body", "html"):
                break
            views.append(parent)
            parent = parent.parent
        item = None
        for node in views:
            node_text = node.get_text(" ", strip=True)
            if not 10 <= len(node_text) <= 650:
                continue
            # Exclude shared containers spanning multiple independent events.
            if sum(name in node_text for name in STATIONS) > 1:
                continue
            if len(re.findall(DATES, node_text)) > 3:
                continue
            # Require an exact station plus two explicit dates in the same
            # limited card. Never use a date found in a different event card.
            entry = extract_hokuriku(node_text, today, href)
            if entry:
                item = entry
                break
        if article_link:
            diagnostics["articleLinks"] += 1
        if not item:
            if article_link:
                diagnostics["unmatchedArticleLinks"] += 1
            continue
        # Only publish a linked official detail page, not calendar-navigation
        # links that happen to be inside an event-card container.
        if not article_link:
            continue
        if link_text and 4 <= len(link_text) <= 100 and not re.search(DATES, link_text):
            if not any(skip in link_text for skip in ("前月", "翌月", "前週", "翌週", "詳細", "もっと見る")):
                item["title"] = link_text
        key = (item["roadName"], item["url"], item["startDate"])
        records[key] = item
        diagnostics["matchedCards"] += 1
    return list(records.values()), diagnostics


def extract_rendered_events(soup, today, page_url):
    """Extract one event at a time from JS-rendered official event cards.

    Require the same small DOM card to contain exactly one known station,
    exactly two explicit dates, and an event title. Never join separate cards.
    """
    candidates = {}
    for node in soup.select("li, article, tr, section, div"):
        value = " ".join(node.stripped_strings)
        if len(value) < 25 or len(value) > 650:
            continue
        stations = [name for name in STATIONS if name in value]
        if len(stations) != 1 or len(re.findall(DATES, value)) != 2:
            continue
        item = extract_hokuriku(value, today, page_url)
        if not item or item["roadName"] != stations[0]:
            continue
        # A link to the specific event is preferred. When the event card is
        # JS-driven without a detail URL, use a date-pinned official calendar.
        source = CALENDAR + "?dc=" + item["startDate"]
        link_title = None
        for a in node.select("a[href]"):
            href = urljoin(page_url, a["href"])
            parsed = urlparse(href)
            if parsed.hostname not in ("www.hokuriku-michinoeki.jp", "hokuriku-michinoeki.jp"):
                continue
            if "/contents/event/" not in parsed.path:
                continue
            qs = parse_qs(parsed.query)
            is_detail = bool(set(qs) - {"dc"}) or parsed.path.rstrip("/") not in (
                "/contents/event", "/contents/event/index.html")
            if not is_detail:
                continue
            source = href
            candidate_title = " ".join(a.stripped_strings)
            if 6 <= len(candidate_title) <= 100 and not re.search(DATES, candidate_title):
                link_title = candidate_title
            break
        item["url"] = source
        if link_title and not any(x in link_title for x in ("戻る", "詳細を見る", "もっと見る")):
            item["title"] = link_title
        else:
            item["title"] = item["title"][:110].strip()
        key = (item["roadName"], item["startDate"], item["endDate"], source)
        # Prefer the smallest unambiguous DOM card instead of an outer wrapper.
        previous = candidates.get(key)
        if previous is None or len(value) < previous[0]:
            candidates[key] = (len(value), item)
    return [pair[1] for pair in candidates.values()]


def create_hokuriku_browser():
    """Chromium on the GitHub Ubuntu runner executes the official CMS scripts."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.page_load_strategy = "eager"
    browser = webdriver.Chrome(options=options)
    browser.set_page_load_timeout(30)
    return browser


def render_hokuriku(browser, url):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import TimeoutException
    browser.get(url)
    try:
        WebDriverWait(browser, 12, poll_frequency=0.8).until(
            lambda b: any(station in b.find_element("tag name", "body").text
                          for station in STATIONS))
    except TimeoutException:
        pass
    return BeautifulSoup(browser.page_source, "html.parser")


AUDIT_FILE = Path(__file__).resolve().parents[1] / "data" / "hokuriku_event_audit.json"

def save_hokuriku_audit(pages, total):
    audit = {"schemaVersion": 1, "pages": pages, "accepted": total}
    content = json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
    if not AUDIT_FILE.exists() or AUDIT_FILE.read_text(encoding="utf-8") != content:
        AUDIT_FILE.write_text(content, encoding="utf-8")

def collect_hokuriku(today):
    found, audits = {}, []
    browser, browser_error = None, None
    # The official homepage typically previews near-future events. The weekly
    # calendar expands coverage after that. Static requests remain diagnostic.
    try:
        for offset in (None, 0, 7, 14, 21, 28, 35):
            day = today + timedelta(days=offset or 0)
            url = CALENDAR + "?dc=" + day.isoformat() if offset is not None else BASE + "/"
            try:
                response = requests.get(url, headers=HEADERS, timeout=15)
                response.raise_for_status()
            except requests.RequestException as exc:
                print(f"北陸公式ページ取得失敗 {url}: {exc}")
                audits.append({"date": day.isoformat(), "url": url, "error": str(exc)[:180]})
                continue
            soup = BeautifulSoup(decode_official_response(response), "html.parser")
            static_records, static_stats = extract_hokuriku_cards(soup, today, response.url)
            rendered_records, browser_html_size, rendered_sample = [], 0, ""
            if not static_records and browser_error is None:
                try:
                    if browser is None:
                        browser = create_hokuriku_browser()
                    rendered = render_hokuriku(browser, url)
                    rendered_sample = rendered.get_text(" ", strip=True)[:450]
                    browser_html_size = len(str(rendered))
                    rendered_records = extract_rendered_events(rendered, today, url)
                except Exception as exc:
                    browser_error = type(exc).__name__ + ": " + str(exc)[:250]
                    print(f"北陸ブラウザ収集失敗: {browser_error}")
            items = static_records + rendered_records
            for item in items:
                key = (item["roadName"], item["startDate"], item["endDate"], item["title"])
                found[key] = item
            page_text = soup.get_text(" ", strip=True)
            scripts = [urljoin(response.url, tag.get("src", "")) for tag in soup.select("script[src]")]
            audits.append({
                "date": day.isoformat(), "url": response.url,
                "htmlSize": len(response.content),
                "stationsInStaticPage": [n for n in STATIONS if n in page_text],
                "staticArticleLinks": static_stats["articleLinks"],
                "staticMatched": len(static_records),
                "browserHtmlSize": browser_html_size,
                "browserMatched": len(rendered_records),
                "browserTextSample": rendered_sample,
                "browserError": browser_error or "",
                "scriptSources": scripts[:15],
            })
            print(f"北陸公式 {day.isoformat()}: HTML={len(static_records)} / "
                  f"ブラウザ表示={len(rendered_records)}")
    finally:
        if browser is not None:
            browser.quit()
        save_hokuriku_audit(audits, len(found))
    return list(found.values())

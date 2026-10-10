"""Discover and inspect official Chubu association event bulletins.

A bulletin has two parallel columns: station-hosted events and nearby events.
Until layout-based venue attribution is verified, never publish its entries.
"""
import io
import re
from urllib.parse import urljoin, urlparse
import requests
import fitz
from bs4 import BeautifulSoup

SOURCE = "https://www.chubu-michinoeki.org/"
HEADERS = {"User-Agent": "MichinotochuRoadEventBot/1.5 (official association bulletin; daily)"}
BULLETIN = re.compile(r"/pdf/20[0-9]{6}event[^/]*[.]pdf$", re.I)
EVENT_LINK = re.compile(r"(?:イベント情報|event)", re.I)
DATE_PATTERN = re.compile(r"(?:[0-9]{1,2}月[0-9]{1,2}日|[0-9]{1,2}月[0-9]{1,2}日)")
MAX_PDF_BYTES = 5_000_000

def bulletin_links(html, base):
    soup = BeautifulSoup(html, "html.parser")
    matches = []
    for a in soup.select("a[href]"):
        href = urljoin(base, a["href"])
        u = urlparse(href)
        if u.scheme != "https" or u.hostname not in ("chubu-michinoeki.org", "www.chubu-michinoeki.org"):
            continue
        label = a.get_text(" ", strip=True)
        if not u.path.lower().endswith(".pdf"):
            continue
        if not (BULLETIN.search(u.path) or EVENT_LINK.search(label)):
            continue
        matches.append(href)
    return list(dict.fromkeys(matches))

def inspect_pdf(content):
    with fitz.open(stream=content, filetype="pdf") as document:
        if len(document) > 20:
            raise ValueError("unexpected PDF page count")
        texts = [page.get_text("text") for page in document]
    blob = "\n".join(texts)
    # Diagnostics only. Station and near-station columns must not be conflated.
    return {"pages": len(texts), "text_chars": len(blob),
            "dated_lines": sum(bool(DATE_PATTERN.search(line)) for line in blob.splitlines()),
            "contains_station_events_heading": "道の駅のイベント" in blob,
            "contains_nearby_events_heading": "周辺地域のイベント" in blob}

def audit_chubu_bulletin():
    try:
        homepage = requests.get(SOURCE, headers=HEADERS, timeout=15)
        homepage.raise_for_status()
        links = bulletin_links(homepage.text, homepage.url)
        if not links:
            print("中部PDF: 公式イベント情報PDFのリンクが未発見（データ維持）")
            return []
        # Latest dated URL first; avoid older bulletins.
        url = sorted(links, reverse=True)[0]
        pdf = requests.get(url, headers=HEADERS, timeout=20)
        pdf.raise_for_status()
        if len(pdf.content) > MAX_PDF_BYTES or not pdf.content.startswith(b"%PDF"):
            raise ValueError("unexpected bulletin payload")
        metrics = inspect_pdf(pdf.content)
        print(f"中部PDF: 発見 {len(links)} / 最新 {url} / "
              f"ページ {metrics['pages']} / 日付入り行 {metrics['dated_lines']} / "
              f"駅内見出し {metrics['contains_station_events_heading']} / "
              f"周辺イベント見出し {metrics['contains_nearby_events_heading']} / "
              "自動登録は会場の列判定ができるまで保留")
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        print(f"中部PDF: 調査失敗（既存データ維持）: {type(exc).__name__}: {exc}")
    return []

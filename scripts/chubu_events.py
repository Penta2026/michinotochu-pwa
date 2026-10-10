"""Discover and inspect official Chubu association event bulletins.

A bulletin has two parallel columns: station-hosted events and nearby events.
Until layout-based venue attribution is verified, never publish its entries.
"""
import io
import json
import re
from pathlib import Path
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


REPORT = Path(__file__).resolve().parents[1] / "data" / "chubu_event_layout_report.json"

def layout_report(content, url):
    """Capture text lines WITH their actual PDF positions, not text flow order."""
    pages = []
    with fitz.open(stream=content, filetype="pdf") as doc:
        for page_no, page in enumerate(doc):
            rows = []
            for block in page.get_text("dict").get("blocks", []):
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    spans = line.get("spans", [])
                    value = "".join(span.get("text", "") for span in spans).strip()
                    if not value:
                        continue
                    box = line.get("bbox", (0, 0, 0, 0))
                    rows.append({"x": round(box[0], 1), "y": round(box[1], 1),
                                 "x2": round(box[2], 1), "text": value[:180]})
            rows.sort(key=lambda row: (round(row["y"] / 6), row["x"]))
            headings = [row for row in rows if "道の駅のイベント" in row["text"] or "周辺地域のイベント" in row["text"]]
            dated = [row for row in rows if DATE_PATTERN.search(row["text"])]
            # The paper has two mirrored tables. Preserve all rows so station\n            # labels can be paired with events inside each table, not across them.\n            for row in rows:\n                x = row["x"]\n                row["section"] = ("left_station" if x < 160 else\n                                  "left_station_event" if x < 400 else\n                                  "left_nearby" if x < 600 else\n                                  "right_station" if x < 755 else\n                                  "right_station_event" if x < 1000 else\n                                  "right_nearby")\n            pages.append({"page": page_no + 1, "width": round(page.rect.width, 1),
                          "height": round(page.rect.height, 1),
                          "headings": headings[:15],
                          "dated_rows": dated[:180],
                          "sample_rows": rows[:36],\n                          "rows": rows,
                          "total_rows": len(rows)})
    return {"schemaVersion": 1, "source": url, "pages": pages}

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
        report = layout_report(pdf.content, url)
        previous = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else None
        if previous != report:
            REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"中部PDF列診断: ページ {len(report['pages'])} / 見出し {sum(len(p['headings']) for p in report['pages'])} / 日付行 {sum(len(p['dated_rows']) for p in report['pages'])}")
        print(f"中部PDF: 発見 {len(links)} / 最新 {url} / "
              f"ページ {metrics['pages']} / 日付入り行 {metrics['dated_lines']} / "
              f"駅内見出し {metrics['contains_station_events_heading']} / "
              f"周辺イベント見出し {metrics['contains_nearby_events_heading']} / "
              "自動登録は会場の列判定ができるまで保留")
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        print(f"中部PDF: 調査失敗（既存データ維持）: {type(exc).__name__}: {exc}")
    return []

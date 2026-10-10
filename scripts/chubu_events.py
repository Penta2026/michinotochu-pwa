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
            # The paper has two mirrored tables. Preserve all rows so station
            # labels can be paired with events inside each table, not across them.
            for row in rows:
                x = row["x"]
                row["section"] = ("left_station" if x < 160 else
                                  "left_station_event" if x < 400 else
                                  "left_nearby" if x < 600 else
                                  "right_station" if x < 755 else
                                  "right_station_event" if x < 1000 else
                                  "right_nearby")
            pages.append({"page": page_no + 1, "width": round(page.rect.width, 1),
                          "height": round(page.rect.height, 1),
                          "headings": headings[:15],
                          "dated_rows": dated[:180],
                          "sample_rows": rows[:36],
                          "rows": rows,
                          "total_rows": len(rows)})
    return {"schemaVersion": 1, "source": url, "pages": pages}


from datetime import date
import unicodedata

# These station names and prefectures have been verified from the association
# bulletin; other stations are deliberately not inferred from nearby columns.
VERIFIED_STATIONS = {"信州新野千石平": "長野県", "遠山郷": "長野県", "飯高駅": "三重県",
                     "古今伝授の里やまと": "岐阜県", "柳津": "岐阜県",
                     "マチテラス日進": "愛知県", "にしお岡ノ山": "愛知県",
                     "奥伊勢木つつ木館": "三重県"}
BULLETIN_DAY = re.compile(r"([0-9]{1,2})月\s*([0-9]{1,2})日")
BULLETIN_END = re.compile(r"^[\s㈪㈫㈬㈭㈮㈯㈰（）()月火水木金土日祝・]*[～〜~－–・-]\s*(?:([0-9]{1,2})月\s*)?([0-9]{1,2})日")
STATION_MARKERS = "❶❷❸❹❺❻❼❽❾❿⓫⓬⓭⓮⓯⓰⓱⓲⓳⓴㉑㉒㉓㉔㉕㊺"

def bulletin_date(text, year):
    value = unicodedata.normalize("NFKC", text)
    start_match = BULLETIN_DAY.search(value)
    if not start_match:
        return None
    month, day = map(int, start_match.groups())
    try:
        first = date(year, month, day)
    except ValueError:
        return None
    last = first
    tail = value[start_match.end():start_match.end()+25]
    end_match = BULLETIN_END.match(tail)
    if end_match:
        em = int(end_match.group(1) or month)
        try:
            last = date(year + (1 if em < month else 0), em, int(end_match.group(2)))
        except ValueError:
            return None
    if not 0 <= (last - first).days <= 31:
        return None
    return first.isoformat(), last.isoformat()

def verified_pdf_events(report, today):
    records = []
    for page in report.get("pages", []):
        # Year must be printed in the same bulletin page, never inferred
        # from the execution date or from an event URL.
        header = " ".join(row["text"] for row in page.get("rows", []) if row["y"] < 40)
        year_match = re.search(r"2\s*0\s*(2\s*[0-9])\s*年", header)
        if not year_match:
            continue
        year = int("20" + re.sub(r"\s", "", year_match.group(1)))
        rows = page["rows"]
        station_rows = []
        for row in rows:
            if row.get("section") not in ("left_station", "right_station"):
                continue
            road = next((name for name in VERIFIED_STATIONS if name in row["text"]), None)
            if road and row["text"].strip().endswith(road) and len(row["text"]) <= len(road) + 3:
                station_rows.append((row, road))
        for row in rows:
            if row.get("section") not in ("left_station_event", "right_station_event"):
                continue
            title = unicodedata.normalize("NFKC", row["text"]).strip()
            if not title.startswith("●") or any(word in title for word in ("中止", "延期", "未定")):
                continue
            side = "left_station" if row["section"] == "left_station_event" else "right_station"
            same_side = [(station, road) for station, road in station_rows if station["section"] == side]
            # Find the preceding station name in the *same* PDF table.
            # Never jump between columns or adopt a nearby-events entry.
            preceding = [(station, road) for station, road in same_side
                         if 0 <= row["y"] - station["y"] <= 65]
            if preceding:
                closest, road = max(preceding, key=lambda item: item[0]["y"])
            else:
                # Legacy safe case: station name explicitly repeated in the
                # event title, with a nearby label that may be printed later.
                repeated = [(station, name) for station, name in same_side
                            if name in title and abs(station["y"] - row["y"]) <= 55]
                if not repeated:
                    continue
                closest, road = min(repeated, key=lambda item: abs(item[0]["y"] - row["y"]))
            # A title naming a DIFFERENT known station is not this station's event.
            if any(name in title and name != road for name in VERIFIED_STATIONS):
                continue
            period = bulletin_date(title, year)
            if not period or period[1] < today.isoformat():
                continue
            records.append({"roadName": road, "prefecture": VERIFIED_STATIONS[road],
                            "title": title, "startDate": period[0], "endDate": period[1],
                            "publishedAt": "", "url": report["source"], "status": "scheduled"})
    return records

def audit_chubu_bulletin(today=None):
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
        events = verified_pdf_events(report, today or date.today())
        print(f"中部PDF: 駅名・開催期間の二重確認済み {len(events)} 件")
        print(f"中部PDF列診断: ページ {len(report['pages'])} / 見出し {sum(len(p['headings']) for p in report['pages'])} / 日付行 {sum(len(p['dated_rows']) for p in report['pages'])}")
        print(f"中部PDF: 発見 {len(links)} / 最新 {url} / "
              f"ページ {metrics['pages']} / 日付入り行 {metrics['dated_lines']} / "
              f"駅内見出し {metrics['contains_station_events_heading']} / "
              f"周辺イベント見出し {metrics['contains_nearby_events_heading']} / "
              "駅名を本文で確認できる催しのみ登録")
        return events
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        print(f"中部PDF: 調査失敗（既存データ維持）: {type(exc).__name__}: {exc}")
    return []

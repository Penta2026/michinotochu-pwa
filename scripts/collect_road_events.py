#!/usr/bin/env python3
"""Collect verified road-station events from official regional listings.

Only events with clear venue and dates are published. Keep past valid records
during temporary fetch failures; never invent dates or event locations.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "road_events.json"
SOURCE = "https://www.sk-michinoeki.jp/events"
NOW = datetime.now(ZoneInfo("Asia/Tokyo")).date()
PREFS = {
    "いたの": "徳島県", "滝宮": "香川県",
    "まきのさんの道の駅・佐川": "高知県",
    "よって西土佐": "高知県", "ことなみ": "香川県",
}
# Expand this verified venue table only after matching names with the app's road database.
ALIASES = {"道の駅いたの":"いたの", "道の駅滝宮":"滝宮",
           "道の駅ことなみ":"ことなみ", "道の駅よって西土佐":"よって西土佐"}
DATE_RE = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")
DATE_LINE = re.compile(r"実施期間\s*(20\d{2}年\s*\d{1,2}月\s*\d{1,2}日[^\n]*)(?:\n|$)")
HEADERS = {"User-Agent":"MichinotochuRoadEventBot/1.0 (public official events; once daily)"}

def format_date(m):
    return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

def get_dates(text):
    found = DATE_RE.findall(text)
    return [f"{int(y):04d}-{int(m):02d}-{int(d):02d}" for y,m,d in found]

def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()

def extract_from_card(card):
    heading = card.find(["h2","h3"])
    if heading is None:
        return None
    link = heading.find("a", href=True)
    if not link:
        return None
    title = clean(link.get_text(" ", strip=True))
    url = urljoin(SOURCE, link["href"])
    if urlparse(url).hostname != "www.sk-michinoeki.jp":
        return None
    text = card.get_text("\n", strip=True)
    # Match event dates ONLY after the '実施期間' label.
    time = text.split("実施期間",1)
    if len(time)<2:
        return None
    dates = get_dates(time[1].split("場",1)[0][:110])
    if not dates:
        return None
    start, end = dates[0], dates[-1]
    if end < NOW.isoformat() or end < start:
        return None
    loc = text.split("場",1)
    if len(loc)<2 or "所" not in loc[1][:15]:
        return None
    venue_lines = [clean(v) for v in loc[1].split("所",1)[1].splitlines() if clean(v)]
    venue = venue_lines[0] if venue_lines else ""
    venue = ALIASES.get(venue,venue)
    if venue not in PREFS:
        return None
    if "中止" in title or "延期" in title:
        return None
    return {"roadName":venue,"prefecture":PREFS[venue],"title":title,
            "startDate":start,"endDate":end,"publishedAt":"",
            "url":url,"status":"scheduled"}

def list_cards(soup):
    # Event cards are marked by their headings; find the narrowest parent
    # containing the date and venue but not multiple other event headings.
    for heading in soup.select("h2,h3"):
        if not heading.find("a",href=True):
            continue
        p = heading
        for _ in range(5):
            p = p.parent
            if not p:
                break
            txt = p.get_text(" ",strip=True)
            if "実施期間" in txt and "場" in txt and "所" in txt:
                if len(p.select("h2,h3")) == 1:
                    yield p
                break

def collect_shikoku():
    result = []
    session = requests.Session()
    for page in range(1,5):
        url = SOURCE if page == 1 else f"{SOURCE}/page/{page}"
        res = session.get(url,timeout=18,headers=HEADERS)
        res.raise_for_status()
        soup = BeautifulSoup(res.text,"html.parser")
        count = 0
        for card in list_cards(soup):
            item=extract_from_card(card)
            if item:
                result.append(item)
                count+=1
        print(f"四国 page {page}: 適合 {count} 件")
        if not soup.find("a", href=re.compile(r"/events/page/"+str(page+1))):
            break
    return result

def main():
    previous=json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    old=previous.get("events",[])
    try:
        collected=collect_shikoku()
    except (requests.RequestException, ValueError) as exc:
        print(f"公式サイト取得失敗。以前の情報を維持: {exc}", file=sys.stderr)
        return 0
    # If page design changed or content unexpectedly empty, preserve previous records.
    if not collected:
        print("照合できるイベントが0件。既存データを維持します。",file=sys.stderr)
        return 0
    # Keep unexpired records from sources not currently collected (e.g. 中国地方).
    preserved=[x for x in old if x.get("endDate","")>=NOW.isoformat() and
               "sk-michinoeki.jp" not in x.get("url","")]
    combined={ (x["url"],x["roadName"]):x for x in preserved+collected}
    final=sorted(combined.values(),key=lambda x:(x["startDate"],x["roadName"],x["title"]))
    # Avoid needless file changes when only collection date differs.
    if final==old:
        print(f"イベント情報は変更なし（{len(final)}件）")
        return 0
    result={"schemaVersion":1,"updatedAt":NOW.isoformat(),"events":final,
            "notes":"公式情報に基づき収集。中国地方は対応する公式収集元を追加中。"}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"イベント更新: {len(final)}件")
    return 0

if __name__=="__main__":
    raise SystemExit(main())

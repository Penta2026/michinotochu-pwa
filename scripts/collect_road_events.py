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
from region_official_events import collect_tohoku
from regional_association_events import collect_regional_associations
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
    loc = time[1].split("場",1)
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


CHUGOKU_SOURCE = "https://chugoku-michinoeki.jp/news/index.php"
CHUGOKU_PREFS = {
    "びんご府中":"広島県","笠岡ベイファーム":"岡山県","みやま公園":"岡山県",
    "ごいせ仁摩":"島根県","あらエッサ":"島根県","サンピコごうつ":"島根県",
    "シルクウェイにちはら":"島根県","キララ多伎":"島根県",
    "西いなば気楽里":"鳥取県","世羅":"広島県",
    "上関海峡":"山口県","おふく":"山口県","北浦街道豊北":"山口県",
    "がいせん桜新庄宿":"岡山県","秋鹿なぎさ公園":"島根県",
    "奥出雲おろちループ":"島根県","三矢の里あきたかた":"広島県",
    "遊YOUさろん東城":"広島県","きららあじす":"山口県"
}
CHUGOKU_DATE_RE = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日|(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?!\d)")
BLOCKED_WORDS = ("中止","延期","休館","休業","営業時間","通行規制","臨時駐車場")
EVENT_WORDS = ("祭","マルシェ","フェア","イベント","抽選","試食","周年","コンサート","公演","販売会")
def chugoku_date(title, announced):
    match=CHUGOKU_DATE_RE.search(title)
    if not match:
        return None
    month=int(match.group(1) or match.group(3))
    day=int(match.group(2) or match.group(4))
    year=announced.year
    # December announcements may refer to next January.
    if announced.month>=11 and month<=2:
        year+=1
    try:
        d=datetime(year,month,day).date()
    except ValueError:
        return None
    if d < NOW or d < announced:
        return None
    return d.isoformat()

def collect_chugoku():
    response=requests.get(CHUGOKU_SOURCE,timeout=18,headers=HEADERS)
    response.raise_for_status()
    soup=BeautifulSoup(response.text,"html.parser")
    found=[]
    for anchor in soup.find_all("a",href=True):
        title=clean(anchor.get_text(" ",strip=True))
        match=re.match(r"^[〖【]([^〗】]+)[〗】]\s*(.+)",title)
        if not match:
            continue
        road=match.group(1).strip()
        if road not in CHUGOKU_PREFS:
            continue
        if any(word in title for word in BLOCKED_WORDS) or not any(word in title for word in EVENT_WORDS):
            continue
        container=anchor.find_parent(["li","tr","article"]) or anchor.parent
        surrounding=clean(container.get_text(" ",strip=True))
        published=re.search(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})",surrounding)
        if not published:
            continue
        try:
            announced=datetime(int(published.group(1)),int(published.group(2)),int(published.group(3))).date()
        except ValueError:
            continue
        start=chugoku_date(match.group(2),announced)
        if not start:
            continue
        href=urljoin(CHUGOKU_SOURCE,anchor["href"])
        if not href.startswith("https://"):
            continue
        # Only one-day events with explicit dates are automatically accepted.
        found.append({"roadName":road,"prefecture":CHUGOKU_PREFS[road],
                      "title":title,"startDate":start,"endDate":start,
                      "publishedAt":announced.isoformat(),"url":href,"status":"scheduled"})
    print(f"中国地方: 日付明記の単日イベント {len(found)} 件")
    return found


# Nationwide official association: conservative single-day or explicitly ranged events.
NATIONAL_SOURCE = "https://www.michi-no-eki.jp/notices"
PREFECTURES = (
    "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 "
    "埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 "
    "岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 "
    "鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 "
    "福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県"
).split()
NATIONAL_ITEM = re.compile(r"^(20\d{2})年(\d{1,2})月(\d{1,2})日\s+(" + "|".join(PREFECTURES) + r")\s+[〖【]道の駅\s*(.+?)[〗】](.+)$")
NATIONAL_DATE = re.compile(r"(?<!\d)(?:(20\d{2})年)?\s*(\d{1,2})月\s*(\d{1,2})日|(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?!\d)")
NATIONAL_SKIP = ("中止","延期","休館","休業","通行規制","交通規制","定休日","休止","売上","営業時間")
NATIONAL_EVENTS = EVENT_WORDS + ("収穫","体験会","フリーマーケット","イルミネーション","夜市","花火","音楽会","文化祭","スタンプラリー","まつり","フェスタ","開催","ワークショップ","特別企画")

def national_event_date(title, published):
    # Announcement date is not an event date; only parse the event-specific title.
    dates = []
    for m in NATIONAL_DATE.finditer(title):
        y = int(m.group(1)) if m.group(1) else published.year
        mo = int(m.group(2) or m.group(4))
        day = int(m.group(3) or m.group(5))
        if not m.group(1) and published.month >= 11 and mo <= 2:
            y += 1
        try:
            dates.append(datetime(y, mo, day).date())
        except ValueError:
            continue
    if not dates:
        return None
    first, last = dates[0], dates[-1]
    if first > last or last < NOW or first < published:
        return None
    # Reject unrelated dates or implausibly broad ranges.
    if (last - first).days > 100:
        return None
    return first.isoformat(), last.isoformat()

def collect_nationwide():
    collected = []
    seen = set()
    counted = {"posts":0,"event_words":0,"dated":0}
    for page in range(0, 9):
        url = NATIONAL_SOURCE if page == 0 else NATIONAL_SOURCE + "?page=" + str(page)
        response = requests.get(url, timeout=18, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        page_posts = 0
        for a in soup.select("a[href]"):
            titletext = clean(a.get_text(" ", strip=True))
            # Date/prefecture are displayed outside the clickable event title on
            # some pages. Read the enclosing list item as well.
            parent = a.find_parent(["li", "article", "tr"])
            context = clean(parent.get_text(" ", strip=True)) if parent else titletext
            match = NATIONAL_ITEM.search(context) or NATIONAL_ITEM.search(titletext)
            if not match:
                continue
            page_posts += 1
            counted["posts"] += 1
            try:
                published = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).date()
            except ValueError:
                continue
            prefecture = match.group(4)
            road = clean(match.group(5)).strip("「」『』 ")
            title = clean(match.group(6))
            if not road or not title or any(w in title for w in NATIONAL_SKIP):
                continue
            if not any(w in title for w in NATIONAL_EVENTS):
                continue
            counted["event_words"] += 1
            period = national_event_date(title, published)
            if not period:
                continue
            counted["dated"] += 1
            href = urljoin(NATIONAL_SOURCE, a["href"])
            if urlparse(href).hostname not in ("www.michi-no-eki.jp", "michi-no-eki.jp"):
                continue
            key = (href, road)
            if key in seen:
                continue
            seen.add(key)
            collected.append({"roadName":road,"prefecture":prefecture,"title":title,
                              "startDate":period[0],"endDate":period[1],
                              "publishedAt":published.isoformat(),"url":href,"status":"scheduled"})
        print(f"全国 page={page} 投稿一致={page_posts}")
        if page_posts == 0:
            break
    print(f"全国公式: 投稿 {counted['posts']} / イベント語句 {counted['event_words']} / 日付あり {counted['dated']} / 採用 {len(collected)}")
    return collected

def main():
    previous=json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    old=previous.get("events",[])
    try:
        shikoku=collect_shikoku()
    except (requests.RequestException, ValueError) as exc:
        print(f"四国の取得失敗。既存データを維持: {exc}", file=sys.stderr)
        shikoku=[]
    try:
        chugoku=collect_chugoku()
    except (requests.RequestException, ValueError) as exc:
        print(f"中国地方の取得失敗。既存データを維持: {exc}", file=sys.stderr)
        chugoku=[]
    try:
        nationwide=collect_nationwide()
    except (requests.RequestException, ValueError) as exc:
        print(f"全国公式の取得失敗。既存データを維持: {exc}", file=sys.stderr)
        nationwide=[]
    try:
        tohoku=collect_tohoku(today=NOW)
    except Exception as exc:
        print(f"東北・各駅公式の取得失敗。既存データを維持: {type(exc).__name__}: {exc}", file=sys.stderr)
        tohoku=[]
    # Regional association sites are primary broad-coverage feeds; individual
    # station sites remain a supplement for notices missing from associations.
    regional=collect_regional_associations(NOW)
    collected=shikoku+chugoku+nationwide+regional+tohoku
    if not collected:
        print("照合できるイベントが0件。既存データを維持します。",file=sys.stderr)
        return 0
    # Incremental merge: a source listing may omit a still-valid event due to
    # pagination, a transient layout change, or an incomplete regional feed.
    # Never delete future verified events merely because another event was found.
    preserved=[x for x in old if x.get("endDate","")>=NOW.isoformat()]
    combined={ (x["url"],x["roadName"]):x for x in preserved+collected}
    final=sorted(combined.values(),key=lambda x:(x["startDate"],x["roadName"],x["title"]))
    # Avoid needless file changes when only collection date differs.
    if final==old:
        print(f"イベント情報は変更なし（{len(final)}件）")
        return 0
    result={"schemaVersion":1,"updatedAt":NOW.isoformat(),"events":final,
            "notes":"公式情報に基づき収集。全国・地域連絡会および各駅の公式サイトから、開催日を確認できた情報を収集。"}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"イベント更新: {len(final)}件")
    return 0

if __name__=="__main__":
    raise SystemExit(main())

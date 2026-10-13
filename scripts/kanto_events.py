"""Collect Kanto association event notices with publication-date grounding."""
import re
import unicodedata
from datetime import date
from pathlib import Path
from station_coverage_registry import read_app_stations, station_key
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

SOURCE = "https://www.kanto-michinoeki.jp/archives/category/イベント情報"
HEADERS = {"User-Agent": "MichinotochuRoadEventBot/1.5 (official notices; daily)"}
MASTER = Path(__file__).resolve().parents[1] / "data" / "app_data.js"

def station_index(roads):
    index = {}
    for r in roads:
        index.setdefault(station_key(r["prefecture"], r["name"])[1], []).append(r)
    return index

def resolve_station(title, index):
    m = STATION.search(title)
    if not m:
        return None
    key = station_key("", m.group(1))[1]
    matches = index.get(key, [])
    return matches[0] if len(matches) == 1 else None

def onsite_venue(body, road):
    """Require an explicit venue label naming this station, not mere mention."""
    key = station_key("", road)[1]
    for line in re.split(r"[\\n。]", body):
        m = re.search(r"(?:開催場所|開催会場|会場|場所)\\s*[：:]\\s*(.{1,100})", line)
        if not m:
            continue
        venue = m.group(1).split("日時", 1)[0]
        station_form = re.search(r"道の駅\\s*[・･]?\\s*([^\\s、,（(]{2,40})", venue)
        if station_form and station_key("", station_form.group(1))[1].startswith(key):
            return True
    return False

TERMS = ("祭","まつり","イベント","マルシェ","フェア","体験","コンサート","収穫")
STATION = re.compile(r"[【〖](?:道の駅\s*)?([^】〗]+)[】〗]")
DATE = re.compile(r"(?:(20\d{2})年)?\s*(\d{1,2})月\s*(\d{1,2})日")
END = re.compile(r"^[\s()月火水木金土日祝・]*[～〜~－–-]\s*(?:(\d{1,2})月\s*)?(\d{1,2})日")
POSTED = re.compile(r"(?<!\d)(\d{2})\.(\d{2})\.(20\d{2})(?!\d)")

def clean(value):
    return " ".join(unicodedata.normalize("NFKC",value or "").split())

def event_period(text, published):
    value=clean(text)
    m=DATE.search(value)
    if not m or (not published and not m.group(1)):
        return None
    year=int(m.group(1)) if m.group(1) else published.year
    month,day=int(m.group(2)),int(m.group(3))
    if not m.group(1) and published.month>=11 and month<=2:
        year+=1
    try:
        start=date(year,month,day)
    except ValueError:
        return None
    tail=value[m.end():m.end()+38]
    follow=END.match(tail)
    end=start
    if follow:
        em=int(follow.group(1)) if follow.group(1) else month
        try:
            end=date(year+(1 if em<month else 0),em,int(follow.group(2)))
        except ValueError:
            return None
    if (published and start<published) or not 0<=(end-start).days<=90:
        return None
    return start.isoformat(),end.isoformat()

def collect_kanto(today):
    session=requests.Session()
    response=session.get(SOURCE,timeout=15,headers=HEADERS)
    response.raise_for_status()
    soup=BeautifulSoup(response.text,"html.parser")
    roads = read_app_stations(MASTER.read_text(encoding="utf-8"))
    index = station_index(roads)
    found=[]; seen=set(); stats={"candidate":0,"unmatched":0,"undated":0,"past":0,"failed":0}
    for a in soup.select("a[href]"):
        url=urljoin(response.url,a["href"])
        if url in seen or not re.search(r"/archives/\d+\.html$",urlparse(url).path):
            continue
        title=clean(a.get_text(" ",strip=True))
        m=STATION.search(title)
        if not m or not any(word in title for word in TERMS):
            continue
        if any(word in title for word in ("中止","延期","休館","休業")):
            continue
        seen.add(url);stats["candidate"]+=1
        station=resolve_station(title, index)
        if station is None:
            stats["unmatched"]+=1
            continue
        try:
            r=session.get(url,timeout=12,headers=HEADERS)
            r.raise_for_status()
            detail=BeautifulSoup(r.text,"html.parser")
        except requests.RequestException:
            stats["failed"]+=1
            continue
        article=detail.select_one("article") or detail.select_one("main") or detail.body
        if article is None:
            stats["undated"]+=1
            continue
        body=clean(article.get_text(" ",strip=True))
        if any(x in body for x in ("開催中止", "イベント中止", "開催を中止", "開催延期")):
            continue
        if not onsite_venue(body, station["name"]):
            stats["unmatched"]+=1
            continue
        stamp=POSTED.search(body)
        if not stamp:
            # Publication marker might be just outside the article wrapper.
            stamp=POSTED.search(clean(detail.get_text(" ",strip=True)))
        try:
            published=date(int(stamp.group(3)),int(stamp.group(1)),int(stamp.group(2))) if stamp else None
        except ValueError:
            published=None
        parsed=event_period(title,published)
        if not parsed:
            for match in re.finditer(r"(?:開催日時|開催日|日時|日程)\s*[：:]?\s*(.{4,75})",body):
                parsed=event_period(match.group(1),published)
                if parsed:break
        if not parsed:
            stats["undated"]+=1
            continue
        if parsed[1]<today.isoformat():
            stats["past"]+=1
            continue
        found.append({"roadName":station["name"],"prefecture":station["prefecture"],"title":title,
                      "startDate":parsed[0],"endDate":parsed[1],
                      "publishedAt":published.isoformat() if published else "","url":url,"status":"scheduled"})
    print(f"関東公式: 候補 {stats['candidate']} / 採用 {len(found)} / 未照合駅 {stats['unmatched']} / 日付未判定 {stats['undated']} / 過去 {stats['past']} / 取得失敗 {stats['failed']}")
    return found

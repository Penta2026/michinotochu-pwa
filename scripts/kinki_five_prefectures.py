"""Conservative station-specific Kinki news coverage for five prefectures.

This is a targeted discovery layer, not evidence of prefecture-wide coverage.
Published events require title-specific/labelled dates with grounded year;
never interpret station opening-hours dates as event dates or month calendars
as month-long events.
"""
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from kyushu_okinawa_events import publication_date

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data/kinki_five_prefectures_audit.json"
HEADERS = {"User-Agent":"MichinotochuRoadEventBot/2.0 (station official Kinki event notices)"}
SOURCES = (
    {"prefecture":"福井県","road":"若狭美浜はまびより",
     "url":"https://hamabiyori.com/events/","host":"hamabiyori.com",
     "path":r"^/(?:events|event|topics|news)/.+", "name":"mihama"},
    {"prefecture":"京都府","road":"和",
     "url":"https://wachi-nagomi.com/topics/category/event/","host":"wachi-nagomi.com",
     "path":r"^/topics/(?!category/|tag/|page/)[^?#]+", "name":"wachi"},
    {"prefecture":"京都府","road":"京丹波 味夢の里",
     "url":"https://ajim.info/","host":"ajim.info",
     "path":r"^/(?:news|event|info)/.+", "name":"ajim"},
    {"prefecture":"大阪府","road":"いずみ山愛の里",
     "url":"https://izuminambu-rc.jp/","host":"izuminambu-rc.jp",
     "path":r"^/(?:event|events|information|news)/.+", "name":"izumi"},
    {"prefecture":"奈良県","road":"クロスウェイなかまち",
     "url":"https://michi-no-eki-crosswaynakamachi.pref.nara.jp/newslist",
     "host":"michi-no-eki-crosswaynakamachi.pref.nara.jp",
     "path":r"^/(?:archives/|events/|news/).+", "name":"nakamachi"},
    {"prefecture":"和歌山県","road":"ねごろ歴史の丘",
     "url":"https://www.negororekishinooka.jp/","host":"www.negororekishinooka.jp",
     "path":r"^/(?:news|event|information|topics)/.+", "name":"negoro"},
)
EVENT_TERMS=("祭","まつり","フェア","マルシェ","マーケット","イベント","公演",
             "演奏","音楽","体験","収穫","実演販売","夜市","展示","催し","講座",
             "宴","猿まわし","教室","食堂")
BLOCK=("中止","延期","募集","応募","締切","求人","定休日","休館","営業時間",
       "休業","イベントカレンダー","イベントスケジュール")
POST_DATE=re.compile(r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})日?")
DATE=re.compile(r"(?:(20\d{2})[年./-])?(\d{1,2})[月./-](\d{1,2})日?(?:\s*[\(（\[]([月火水木金土日])(?:[^)）\]]{0,7})[\)）\]])?")
END=re.compile(r"^\s*(?:[～〜~▶▷\-－–]|から|より)\s*(?:(\d{1,2})[月./-])?(\d{1,2})日?(?:\s*[\(（\[]([月火水木金土日])(?:[^)）\]]{0,7})[\)）\]])?")
LABEL=re.compile(r"(?:(?:開催|実施|公演)(?:日|日時|期間)|日程|日時|開催予定)\s*[:：]?\s*")
WEEKDAYS="月火水木金土日"

def clean(value):
    return " ".join(unicodedata.normalize("NFKC", value or "").split())

def date_of(y,m,d,weekday=""):
    try:
        out=date(int(y),int(m),int(d))
        if weekday and WEEKDAYS[out.weekday()]!=weekday:
            return None
        return out
    except (ValueError, TypeError):
        return None

def event_period(text, posted=None):
    value=clean(text)
    m=DATE.search(value)
    if not m:
        return None
    yy=int(m.group(1)) if m.group(1) else (posted.year if posted else None)
    if yy is None:
        return None
    month=int(m.group(2))
    if not m.group(1) and posted and posted.month>=11 and month<=2:
        yy+=1
    first=date_of(yy, month, m.group(3),m.group(4) or "")
    if not first:
        return None
    last=first
    rem=value[m.end():m.end()+40]
    mm=END.match(rem)
    if mm:
        month_end=int(mm.group(1)) if mm.group(1) else month
        last=date_of(yy+(1 if month_end<month else 0),
                     month_end,mm.group(2),mm.group(3) or "")
        if not last:
            return None
    if last<first or (last-first).days>90:
        return None
    return first.isoformat(),last.isoformat()

def _get(url):
    r=requests.get(url,timeout=13,headers=HEADERS)
    r.raise_for_status()
    if not r.encoding or r.encoding.lower()=="iso-8859-1":
        r.encoding=r.apparent_encoding
    return BeautifulSoup(r.text,"html.parser")

def _candidates(spec,soup):
    items={}
    for a in soup.select("a[href]"):
        text=clean(a.get_text(" ",strip=True))
        url=urljoin(spec["url"],a.get("href",""))
        u=urlparse(url)
        if u.scheme!="https" or u.hostname!=spec["host"] or not re.match(spec["path"],u.path):
            continue
        if not 7<=len(text)<=155 or not any(w in text for w in EVENT_TERMS):
            continue
        if any(w in text for w in BLOCK):
            continue
        # Publication date is only grounding information, not an event date.
        parent=a.find_parent(["article","li","tr"]) or a.parent
        context=clean(parent.get_text(" ",strip=True)) if parent else text
        matches=POST_DATE.search(context[:175])
        stamp=date_of(*matches.groups()) if matches else None
        items.setdefault(url,{"title":text,"published":stamp})
        if len(items)>=16:
            break
    return items

def _article_title(soup,fallback):
    for css in ("article h1","main h1","h1","article h2","main h2","h2"):
        h=soup.select_one(css)
        name=clean(h.get_text(" ",strip=True)) if h else ""
        if name and any(w in name for w in EVENT_TERMS) and not any(w in name for w in BLOCK):
            return name
    return fallback

def _article_date(spec,title,soup,posted):
    if any(w in title for w in BLOCK):
        return None
    p=event_period(title,posted)
    if p:
        return p
    body=soup.select_one("article") or soup.select_one("main") or soup
    lines=body.get_text("\n",strip=True).splitlines()
    for i,line in enumerate(lines):
        l=clean(line)
        if len(l)>175:
            continue
        m=LABEL.search(l[:35])
        if m:
            snippet=l[m.end():]
            if not snippet and i+1<len(lines):
                snippet=clean(lines[i+1])
            p=event_period(snippet,posted)
            if p:
                return p
    return None

def _venue_ok(spec,title,soup):
    # The five station-owned feeds generally establish the station identity;
    # Izumi's page is a broader multipurpose public complex.
    if spec["name"]!="izumi":
        return True
    body=clean((soup.select_one("article") or soup.select_one("main") or soup).get_text(" ",strip=True))
    return bool(re.search(r"(?:会場|開催場所|開催地)\s*[:：]?\s*(?:道の駅いずみ山愛の里|南部リージョンセンター)",body))

def collect_kinki_five(today):
    out, audits=[],[]
    for spec in SOURCES:
        stats={"prefecture":spec["prefecture"],"roadName":spec["road"],
               "url":spec["url"],"listingError":"","candidates":0,"checked":0,
               "accepted":0,"past":0,"undated":0,"venueMismatch":0,
               "failed":0,"examples":[],"undatedExamples":[]}
        try:
            listing=_get(spec["url"])
            links=_candidates(spec,listing)
        except requests.RequestException as e:
            links={}
            stats["listingError"]=f"{type(e).__name__}: {str(e)[:160]}"
        stats["candidates"]=len(links)
        for url,entry in list(links.items())[:12]:
            try:
                soup=_get(url)
            except requests.RequestException:
                stats["failed"]+=1
                continue
            stats["checked"]+=1
            title=_article_title(soup,entry["title"])
            posted=publication_date(soup,title) or entry["published"]
            period=_article_date(spec,title,soup,posted)
            if not period:
                stats["undated"]+=1
                if len(stats["undatedExamples"])<4:
                    stats["undatedExamples"].append({"title":title,"url":url})
                continue
            if period[1]<today.isoformat():
                stats["past"]+=1
                continue
            if not _venue_ok(spec,title,soup):
                stats["venueMismatch"]+=1
                continue
            record={"roadName":spec["road"],"prefecture":spec["prefecture"],
                    "title":title,"startDate":period[0],"endDate":period[1],
                    "publishedAt":posted.isoformat() if posted else "",
                    "url":url,"status":"scheduled"}
            out.append(record)
            stats["accepted"]+=1
            if len(stats["examples"])<5:
                stats["examples"].append({"title":title,"start":period[0],"end":period[1],"url":url})
        audits.append(stats)
        print(f"近畿5府県 {spec['prefecture']} {spec['road']}: "
              f"候補={stats['candidates']} 採用={stats['accepted']} "
              f"日付未確定={stats['undated']} 取得失敗={stats['failed']}")
    unique={(e["prefecture"],e["roadName"],e["url"],e["startDate"]):e for e in out}
    report={"schemaVersion":1,"sources":audits,"accepted":len(unique)}
    payload=json.dumps(report,ensure_ascii=False,indent=2)+"\n"
    if not REPORT.exists() or REPORT.read_text(encoding="utf-8")!=payload:
        REPORT.write_text(payload,encoding="utf-8")
    return list(unique.values())

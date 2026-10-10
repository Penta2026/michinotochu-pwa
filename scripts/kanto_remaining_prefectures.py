"""Official three-prefecture Kanto station news feeds (Chiba, Tokyo, Kanagawa).

Only an event-specific notice with a grounded date is published. Station
calendars and recruitment deadlines are NOT treated as event periods.
Offsite events where a station is only a checkpoint are not station events.
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
from kanto_three_prefectures import parse_period as kanto_period

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "kanto_remaining_prefectures_audit.json"
SOURCES = (
    {"key":"shonan", "prefecture":"千葉県", "road":"しょうなん",
     "url":"https://www.michinoeki-shonan.jp/",
     "hosts":("www.michinoeki-shonan.jp","michinoeki-shonan.jp"),
     "path":r"^/news/\d+/?$",
     "seed":("https://www.michinoeki-shonan.jp/news/3181/",
             "https://www.michinoeki-shonan.jp/news/3174/",
             "https://www.michinoeki-shonan.jp/news/3170/")},
    {"key":"hotasho", "prefecture":"千葉県", "road":"保田小学校",
     "url":"https://hotasho.jp/news-list/", "hosts":("hotasho.jp",),
     "path":r"^/(?:20\d{2}/\d{2}/)?[^?#]+/?$", "seed":()},
    {"key":"hachioji", "prefecture":"東京都", "road":"八王子滝山",
     "url":"https://www.michinoeki-hachioji.net/category/news",
     "hosts":("www.michinoeki-hachioji.net","michinoeki-hachioji.net"),
     "path":r"^/news/\d+/?$", "seed":()},
    {"key":"chigasaki", "prefecture":"神奈川県", "road":"湘南ちがさき",
     "url":"https://m-shonanchigasaki.com/topics/",
     "hosts":("m-shonanchigasaki.com","www.m-shonanchigasaki.com"),
     "path":r"^/topics/detail\.php$", "seed":()},
)
HEADERS={"User-Agent":"MichinotochuRoadEventBot/1.9 (official station event news)"}
EVENT_WORDS=("イベント","フェア","祭","まつり","フォトDAY","鷹匠","マルシェ",
             "マーケット","体験","コンサート","開園祭","物産展","ツアー","公演","ライブ")
SKIP=("募集","応募","締切","休館","定休日","臨時休業","営業のお知らせ","中止",
      "延期","終了しました","参加者募集","年間スケジュール")
DATE_TOKEN=re.compile(r"(?:(20\d{2})[年./-]\s*)?(\d{1,2})[月./-]\s*(\d{1,2})日?(?:\s*\(([月火水木金土日])(?:[^)]{0,6})\))?")
DATE_POST=re.compile(r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})日?")
RANGE_END=re.compile(r"^\s*[～〜~▶▷\-－–・、]\s*(?:(\d{1,2})[月./-])?\s*(\d{1,2})日?(?:\s*\(([月火水木金土日])(?:[^)]{0,6})\))?")
LABEL=re.compile(r"(?:開催日時|開催期間|開催日|イベント日時|日程|日にち|日時)\s*[:：]?\s*")
WEEKDAYS="月火水木金土日"

def clean(value):
    return " ".join(unicodedata.normalize("NFKC",value or "").split())

def safe_date(y,m,d,weekday=""):
    try:
        result=date(int(y),int(m),int(d))
    except (ValueError,TypeError):
        return None
    if weekday and WEEKDAYS[result.weekday()]!=weekday:
        return None
    return result

def event_period(value, published=None):
    """Explicit range including 2026.10.10~12 or 10月10日 with article year."""
    value=clean(value)
    first=DATE_TOKEN.search(value)
    if first is None:
        return None
    yy=int(first.group(1)) if first.group(1) else (published.year if published else None)
    if yy is None:
        return None
    mm=int(first.group(2))
    if not first.group(1) and published and published.month>=11 and mm<=2:
        yy+=1
    start=safe_date(yy,mm,first.group(3),first.group(4) or "")
    if not start:
        return None
    end=start
    tail=value[first.end():first.end()+36]
    m=RANGE_END.match(tail)
    if m:
        em=int(m.group(1)) if m.group(1) else mm
        end=safe_date(start.year+(1 if em<mm else 0),em,m.group(2),m.group(3) or "")
    else:
        m2=DATE_TOKEN.match(tail.lstrip("~～〜-－– ▶▷"))
        if m2 and re.match(r"^\s*[～〜~▶▷\-－–]",tail):
            em=int(m2.group(2))
            end=safe_date(int(m2.group(1)) if m2.group(1) else
                          start.year+(1 if em<mm else 0),em,m2.group(3),m2.group(4) or "")
    if end is None or end<start or (end-start).days>90:
        return None
    return start.isoformat(),end.isoformat()

def _get(url):
    r=requests.get(url,headers=HEADERS,timeout=13)
    r.raise_for_status()
    if not r.encoding or r.encoding.lower()=="iso-8859-1":
        r.encoding=r.apparent_encoding
    return BeautifulSoup(r.text,"html.parser")

def candidates(spec,soup):
    links={}
    for a in soup.select("a[href]"):
        title=clean(a.get_text(" ",strip=True))
        if len(title)<5:
            continue
        href=urljoin(spec["url"],a.get("href",""))
        parsed=urlparse(href)
        if parsed.scheme!="https" or parsed.hostname not in spec["hosts"]:
            continue
        if not re.match(spec["path"],parsed.path):
            continue
        if spec["key"]=="hotasho" and not any(term in title for term in EVENT_WORDS):
            continue
        if any(term in title for term in SKIP):
            continue
        if spec["key"]=="hachioji" and not any(term in title for term in EVENT_WORDS):
            continue
        if spec["key"]=="chigasaki" and "EVENT" not in title and not any(
            term in title for term in EVENT_WORDS):
            continue
        # Avoid treating article publication date in a large surrounding card
        # as an event date. It is used only to ground title month/day.
        card=a.find_parent(["li","article","tr"]) or a.parent
        context=clean(card.get_text(" ",strip=True)) if card else title
        links.setdefault(href,{"headline":title,"context":context[:280]})
        if len(links)>=22:
            break
    for url in spec.get("seed",()):
        links.setdefault(url,{"headline":"","context":""})
    return links

def _first_title(spec,soup,fallback):
    for selector in ("article h1","main h1","h1","article h2","main h2","h2"):
        node=soup.select_one(selector)
        value=clean(node.get_text(" ",strip=True)) if node else ""
        if value and value not in ("お知らせ","TOPICS","最新情報","イベント情報"):
            return value
    # Preserve real listing headline when article header is templated/empty.
    return re.sub(r"^(?:EVENT\s*)?(?:20\d{2}[./-]\d{2}[./-]\d{2}\s*)?",
                  "",clean(fallback),flags=re.I)

def article_event_period(spec,title,body,published):
    if not any(word in title for word in EVENT_WORDS) or any(w in title for w in SKIP):
        return None
    # Calendar announcements mostly display an image; publication month is
    # NOT a period covering every day in that month.
    if "カレンダー" in title or "スケジュール" in title:
        return None
    if spec["key"]=="shonan" and "全国造園フェスティバル" in title:
        # Official page says the venue is 手賀沼自然ふれあい緑道 and the
        # station is merely one quiz-rally checkpoint.
        return None
    # Strongest evidence: full-year range in title, including dot notation.
    p=event_period(title,published)
    if p:
        return p
    # Event-specific title may have only month/day (year is publishedAt).
    if published:
        p=event_period(title,published)
        if p:
            return p
    # Body needs an explicit event-date LABEL. Do not take unrelated opening
    # dates, application deadlines, last year's schedule or footer timestamps.
    for line in re.split(r"[\n。]|(?=【[^】]{1,16}】)", body):
        value=clean(line)
        match=LABEL.search(value[:65])
        if match:
            p=event_period(value[match.end():match.end()+90],published)
            if p:
                return p
    return None

def parse_one(spec,title,soup,published,today,url):
    head=_first_title(spec,soup,title)
    if not head or any(w in head for w in SKIP):
        return None,"skipped"
    article=soup.select_one("article") or soup.select_one("main") or soup
    body=clean(article.get_text(" ",strip=True))
    # Keep only actual road-station news articles, not external event pages
    # mirroring other venues. The station is established by source domain.
    period=article_event_period(spec,head,body,published)
    if not period:
        return None,"undated"
    if period[1]<today.isoformat():
        return None,"past"
    record={"roadName":spec["road"],"prefecture":spec["prefecture"],"title":head,
            "startDate":period[0],"endDate":period[1],
            "publishedAt":published.isoformat() if published else "",
            "url":url,"status":"scheduled"}
    return record,"accepted"

def collect_kanto_remaining(today):
    records, audits=[],[]
    for spec in SOURCES:
        a={"key":spec["key"],"prefecture":spec["prefecture"],"station":spec["road"],
           "source":spec["url"],"listingError":"","candidates":0,
           "checked":0,"accepted":0,"past":0,"undated":0,
           "skipped":0,"errors":0,"examples":[],"undatedExamples":[]}
        try:
            listing=_get(spec["url"])
            links=candidates(spec,listing)
        except requests.RequestException as exc:
            a["listingError"]=f"{type(exc).__name__}: {str(exc)[:135]}"
            links={url:{"headline":"","context":""} for url in spec.get("seed",())}
        a["candidates"]=len(links)
        for url,data in list(links.items())[:24]:
            try:
                detail=_get(url)
            except requests.RequestException:
                a["errors"]+=1
                continue
            a["checked"]+=1
            title=_first_title(spec,detail,data["headline"])
            pub=publication_date(detail,title)
            # Short dates in list items can be publication metadata but
            # never treat that day as the event itself.
            if pub is None:
                stamp=DATE_POST.search(data["context"][:80])
                pub=safe_date(*stamp.groups()) if stamp else None
            record,why=parse_one(spec,data["headline"],detail,pub,today,url)
            if record:
                records.append(record)
                a["accepted"]+=1
                if len(a["examples"])<8:
                    a["examples"].append({"title":record["title"],"start":record["startDate"],"end":record["endDate"],"url":url})
            else:
                a[why]+=1
                if why=="undated" and len(a["undatedExamples"])<4:
                    a["undatedExamples"].append({"title":title,"url":url})
        audits.append(a)
        print(f"関東残り {spec['prefecture']} {spec['road']}: "
              f"候補={a['candidates']} 採用={a['accepted']} "
              f"日付不明={a['undated']} エラー={a['errors']}")
    unique={(r["prefecture"],r["roadName"],r["url"],r["startDate"]):r for r in records}
    report={"schemaVersion":1,"sources":audits,"accepted":len(unique)}
    payload=json.dumps(report,ensure_ascii=False,indent=2)+"\n"
    if not REPORT.exists() or REPORT.read_text(encoding="utf-8")!=payload:
        REPORT.write_text(payload,encoding="utf-8")
    return list(unique.values())

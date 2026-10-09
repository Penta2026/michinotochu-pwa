"""Official roadside station site collectors, starting with Tohoku.

Do not infer an event end date from publication time or unrelated contests.
Sources are station-managed websites; each handler can be expanded independently.
"""
import re
from datetime import date
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

APPLE_HILL = "https://www.applehill.co.jp/"
USER_AGENT = {"User-Agent": "MichinotochuRoadEventBot/1.1 (official public notices; daily)"}

def _clean(value):
    return re.sub(r"\s+", " ", value or "").strip()

def _date(year, month, day):
    return date(int(year), int(month), int(day)).isoformat()

def _apple_hill_period(text):
    # Date is explicitly introduced with 日時, not taken from unrelated
    # contest submissions or the publication timestamp.
    match = re.search(r"日時\s*[:：]\s*(?:令和\s*(\d+)\s*年|(20\d{2})\s*年)\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if not match:
        return None
    year = (2018 + int(match.group(1))) if match.group(1) else int(match.group(2))
    month = int(match.group(3))
    day = int(match.group(4))
    try:
        start = date(year, month, day)
    except ValueError:
        return None
    rest = text[match.end():match.end()+55]
    # For "10月17日(土)・18日(日)" find the second day; for a full
    # "10月17日〜11月2日" range use the next explicit month.
    end = start
    second = re.search(r"\s*[・〜～\-]\s*(?:(\d{1,2})\s*月\s*)?(\d{1,2})\s*日", re.sub(r"\([^)]*\)", "", rest))
    if second:
        try:
            em = int(second.group(1)) if second.group(1) else month
            ey = year + (1 if em < month else 0)
            end = date(ey, em, int(second.group(2)))
        except ValueError:
            return None
    if end < start or (end - start).days > 100:
        return None
    return start.isoformat(), end.isoformat()


MURATA_NEWS = "https://muratamachi.info/category/news"
OYU_FES = "https://yunoeki-oyu.jp/information/kuromanta-rock-fes/"
DATE_RANGE = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日.{0,25}?[～〜~\-].{0,12}?(?:(\d{1,2})月)?\s*(\d{1,2})日")
DATE_START = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")

def _explicit_period(content):
    m = DATE_RANGE.search(content)
    if m:
        year, month, day, endmonth, endday = m.groups()
        try:
            begin = date(int(year),int(month),int(day))
            em = int(endmonth) if endmonth else int(month)
            end = date(int(year)+(1 if em<int(month) else 0),em,int(endday))
            if 0 <= (end-begin).days <= 100:
                return begin.isoformat(),end.isoformat()
        except ValueError:
            return None
    m = DATE_START.search(content)
    if m:
        try:
            d = date(*map(int,m.groups()))
            return d.isoformat(),d.isoformat()
        except ValueError:
            return None
    return None

def _record(road, pref, title, period, url):
    return {"roadName":road,"prefecture":pref,"title":title,
            "startDate":period[0],"endDate":period[1],
            "publishedAt":"","url":url,"status":"scheduled"}

def collect_oyu(today):
    r=requests.get(OYU_FES, timeout=18, headers=USER_AGENT)
    r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser")
    # The station's official article unambiguously names the event and venue.
    body=_clean(soup.get_text(" ",strip=True))
    if "クロマンタ" not in body or "道の駅おおゆ" not in body:
        print("東北・おおゆ: 公式記事の会場・イベント名を確認できず")
        return []
    match=re.search(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日",body)
    if not match:
        return []
    try:
        d=date(*map(int,match.groups())).isoformat()
    except ValueError:
        return []
    return [_record("おおゆ","秋田県","クロマンタROCK-FES",(d,d),OYU_FES)] if d>=today.isoformat() else []

def collect_murata(today):
    r=requests.get(MURATA_NEWS,timeout=18,headers=USER_AGENT)
    r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser")
    events=[]
    # WordPress news usually groups each notice inside an article; keep the
    # text local to one article to avoid borrowing dates from other posts.
    for article in soup.select("article"):
        heading=article.find(["h1","h2","h3","h4"])
        if not heading:
            continue
        title=_clean(heading.get_text(" ",strip=True))
        if not title or not any(w in title for w in ("祭り","まつり","展","マルシェ","フェア","イベント","大会")):
            continue
        body=_clean(article.get_text(" ",strip=True))
        if "道の駅" not in body or "村田" not in body:
            continue
        period=_explicit_period(body)
        if not period or period[1] < today.isoformat():
            continue
        anchor=heading.find("a",href=True)
        url=urljoin(MURATA_NEWS,anchor["href"]) if anchor else MURATA_NEWS
        if urlparse(url).hostname not in ("muratamachi.info","www.muratamachi.info"):
            continue
        events.append(_record("村田","宮城県",title,period,url))
    print(f"東北・道の駅村田: 採用 {len(events)} 件")
    return events

def collect_tohoku(today=None):
    today = today or date.today()
    home = requests.get(APPLE_HILL, timeout=18, headers=USER_AGENT)
    home.raise_for_status()
    soup = BeautifulSoup(home.text, "html.parser")
    candidates = []
    for link in soup.select('a[href*="infodetail"]'):
        # Detail links often have generic text such as 「詳細はこちら」.
        href = urljoin(APPLE_HILL, link.get("href", ""))
        if urlparse(href).hostname != "www.applehill.co.jp":
            continue
        if href not in candidates:
            candidates.append(href)
    events = []
    for href in candidates[:20]:
        page = requests.get(href, timeout=18, headers=USER_AGENT)
        page.raise_for_status()
        detail = BeautifulSoup(page.text, "html.parser")
        content = _clean(detail.get_text(" ",strip=True))
        if "アップルヒル秋の大収穫祭" not in content and "アップルヒル 秋の大収穫祭" not in content:
            continue
        period = _apple_hill_period(content)
        if not period or period[1] < today.isoformat():
            continue
        events.append({"roadName":"なみおか","prefecture":"青森県",
            "title":"アップルヒル秋の大収穫祭",
            "startDate":period[0],"endDate":period[1],
            "publishedAt":"","url":href,"status":"scheduled"})
    print(f"東北・道の駅なみおか: 告知候補 {len(candidates)} / 採用 {len(events)}")
    for name, collector in (("おおゆ",collect_oyu),("村田",collect_murata)):
        try:
            events.extend(collector(today))
        except (requests.RequestException,ValueError) as exc:
            print(f"東北・{name} の収集失敗（他の駅は継続）: {exc}")
    return events

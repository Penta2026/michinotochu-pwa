"""Conservative generic collector for regional association news articles.

Only pages naming a specific station, prefecture, and explicitly labelled
event dates are published. Ambiguous PDFs and regional (multi-station) events
remain discovery candidates rather than fabricated station events.
"""
import re
import unicodedata
from datetime import date
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from nationwide_source_audit import SOURCES, HEADERS

ENABLED = {"北海道", "関東", "北陸", "中部", "九州・沖縄"}
PREFS = "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県".split()
EVENTS = ("祭", "マルシェ", "イベント", "フェス", "収穫", "音楽", "展", "フェア", "体験", "花火", "ワークショップ")
BLOCK = ("中止", "延期", "休館", "休業", "臨時休業", "募集", "オープン", "スタンプラリー")
DATE = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")
END = re.compile(r"^[\s（()）月火水木金土日祝・]*[～〜~－–-]\s*(?:(\d{1,2})月\s*)?(\d{1,2})日")
STATION = re.compile(r"道の駅\s*[「『]?([^」』\s（(、,。]{2,35})")
LABEL = re.compile(r"(?:開催期間|開催日時|開催日|イベント日時|日時|日程)\s*[：:]?\s*(.{0,95})")
LIMIT = 8

def clean(value):
    return " ".join((value or "").split())

def period(value):
    normalized = unicodedata.normalize("NFKC", value).replace("~", "～")
    m = DATE.search(normalized)
    if not m:
        return None
    try:
        y, mo, da = map(int, m.groups())
        first = date(y, mo, da)
        tail = normalized[m.end():m.end()+40]
        endmatch = END.match(tail)
        if endmatch:
            em = int(endmatch.group(1)) if endmatch.group(1) else mo
            ey = y + (1 if em < mo else 0)
            last = date(ey, em, int(endmatch.group(2)))
        else:
            last = first
        if not 0 <= (last - first).days <= 90:
            return None
        return first.isoformat(), last.isoformat()
    except ValueError:
        return None

def labelled_period(soup):
    for element in soup.select("main p,main li,main dd,main td,article p,article li,article dd,article td"):
        text = clean(element.get_text(" ", strip=True))
        if len(text) > 350:
            continue
        match = LABEL.search(text)
        if match:
            p = period(match.group(1))
            if p:
                return p
    return None

def collect_generic_regions(today):
    records = []
    for source in SOURCES:
        region = source["region"]
        if region not in ENABLED:
            continue
        stats = {"candidate": 0, "parsed": 0, "missing_date": 0, "missing_station": 0, "missing_pref": 0, "error": 0}
        try:
            response = requests.get(source["url"], headers=HEADERS, timeout=8)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as exc:
            print(f"全国補完 {region}: 一覧取得失敗 {exc}")
            continue
        candidates = {}
        host = urlparse(response.url).hostname
        discovered = 0
        for a in soup.select("a[href]"):
            title = clean(a.get_text(" ", strip=True))
            if not 6 <= len(title) <= 160 or not any(w in title for w in EVENTS):
                continue
            if any(w in title for w in BLOCK):
                continue
            href = urljoin(response.url, a["href"])
            if urlparse(href).hostname != host or href == response.url:
                continue
            context = clean((a.find_parent(["li", "article"]) or a.parent).get_text(" ", strip=True))
            discovered += 1
            candidates.setdefault(href, (title, context))
            if len(candidates) >= LIMIT:
                break
        stats["candidate"] = len(candidates)
        print(f"全国補完 {region}: イベント語句リンク {discovered} / 詳細対象 {len(candidates)}")
        for url, (title, context) in candidates.items():
            try:
                res = requests.get(url, headers=HEADERS, timeout=8)
                res.raise_for_status()
                detail = BeautifulSoup(res.text, "html.parser")
            except requests.RequestException:
                stats["error"] += 1
                continue
            body_node = detail.select_one("article") or detail.select_one("main")
            if body_node is None:
                stats["missing_station"] += 1
                continue
            content = clean(body_node.get_text(" ", strip=True))
            station_match = STATION.search(title) or STATION.search(context)
            if not station_match:
                heading = detail.find(["h1", "h2"])
                station_match = STATION.search(clean(heading.get_text(" ", strip=True))) if heading else None
            if not station_match:
                stats["missing_station"] += 1
                continue
            road = station_match.group(1).strip("「」『』・:：")
            if road in ("イベント", "まつり", "情報", "一覧", "連絡会") or len(road) > 26:
                stats["missing_station"] += 1
                continue
            prefecture = next((p for p in PREFS if p in context or p in title), None)
            if not prefecture:
                # Prefer article body scoped to the actual announcement.
                prefecture = next((p for p in PREFS if p in content[:900]), None)
            if not prefecture:
                stats["missing_pref"] += 1
                continue
            dates = labelled_period(detail)
            if not dates:
                stats["missing_date"] += 1
                continue
            if dates[1] < today.isoformat():
                continue
            records.append({"roadName": road, "prefecture": prefecture,
                            "title": title, "startDate": dates[0], "endDate": dates[1],
                            "publishedAt": "", "url": url, "status": "scheduled"})
            stats["parsed"] += 1
        print(f"全国補完 {region}: 候補 {stats['candidate']} / 採用 {stats['parsed']} / "
              f"駅名不明 {stats['missing_station']} / 県名不明 {stats['missing_pref']} / "
              f"開催日不明 {stats['missing_date']} / 取得失敗 {stats['error']}")
    return records

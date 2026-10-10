"""Regional road-station association feeds.

Conservative rules: only publish a station-specific event with an explicit
calendar date and official page URL. A notice's publication date is never
mistaken for its event date.
"""
import re
from datetime import date
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "MichinotochuRoadEventBot/1.2 (public association notices; daily)"}
TOHOKU = "https://www.michinoeki-tohoku.com/event"
KINKI = "https://www.kinki-michinoeki.com/news-tag/event/"
PREFS = ("北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 "
         "千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 "
         "静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 "
         "島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 "
         "長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県").split()
EVENT_WORDS = ("祭", "フェス", "マルシェ", "イベント", "展示", "販売会",
               "収穫", "コンサート", "音楽", "体験", "イルミネーション",
               "フェア", "夜市", "花火", "ワークショップ")
SKIP = ("中止", "延期", "休業", "休館", "オープン", "開駅", "閉館")
FULL_DATE = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")
SHORT_DATE = re.compile(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*日|(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)")
RANGE_END = re.compile(r"^[^\n]{0,16}?[～〜~－–-]\s*(?:(\d{1,2})\s*月\s*)?(\d{1,2})\s*日")


def _clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _date(y, m, d):
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def _period(value, published=None):
    """Parse dates from event field/title only, not page-wide dates."""
    full = FULL_DATE.search(value)
    short = SHORT_DATE.search(value)
    if full and (not short or full.start() <= short.start()):
        start = _date(*full.groups())
        tail = value[full.end():full.end()+35]
    elif short and published:
        mm = short.group(1) or short.group(3)
        dd = short.group(2) or short.group(4)
        y = published.year + (1 if published.month >= 11 and int(mm) <= 2 else 0)
        start = _date(y, mm, dd)
        tail = value[short.end():short.end()+35]
    else:
        return None
    if not start:
        return None
    end = start
    normalized = re.sub(r"[（(][^）)]{1,12}[）)]", "", tail)
    m = RANGE_END.match(normalized)
    if m:
        em = int(m.group(1)) if m.group(1) else start.month
        ey = start.year + (1 if em < start.month else 0)
        end = _date(ey, em, m.group(2))
    if not end or (end - start).days < 0 or (end - start).days > 90:
        return None
    return start.isoformat(), end.isoformat()


def _record(road, pref, title, period, url, published=""):
    return {"roadName": road, "prefecture": pref, "title": title,
            "startDate": period[0], "endDate": period[1],
            "publishedAt": published, "url": url, "status": "scheduled"}


def _get(url):
    response = requests.get(url, timeout=18, headers=HEADERS)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def collect_tohoku_association(today):
    """Tohoku association's own event-listing page.

    Many entries are station opening announcements, deliberately excluded.
    """
    soup = _get(TOHOKU)
    results = []
    seen = set()
    for anchor in soup.select("a[href]"):
        text = _clean(anchor.get_text(" ", strip=True))
        if "開催期間" not in text or not any(w in text for w in EVENT_WORDS):
            continue
        if any(w in text for w in SKIP):
            continue
        href = urljoin(TOHOKU, anchor["href"])
        if urlparse(href).hostname not in ("www.michinoeki-tohoku.com", "michinoeki-tohoku.com"):
            continue
        section = text.split("開催期間", 1)
        period = _period(section[1])
        if not period or period[1] < today.isoformat():
            continue
        # No single station can be assigned to multi-station festivals.
        name = re.search(r"道の駅[・「\s]*([^」(（\s]+)", section[0])
        pref = next((p for p in PREFS if p in section[0]), None)
        if not name or not pref:
            continue
        road = name.group(1).rstrip("！!")
        key = (href, road)
        if key in seen:
            continue
        seen.add(key)
        results.append(_record(road, pref, section[0], period, href))
    print(f"東北連絡会: 採用 {len(results)} 件")
    return results


def _kinki_article_period(title, detail, published=None):
    """Use labelled event dates, never article publication dates."""
    published = _publication_date(detail) or published
    period = _period(title, published)
    if period:
        return period
    # Article body: inspect labelled date snippets rather than the complete
    # page (whose header/footer may contain unrelated dates).
    for node in detail.find_all(["p", "li", "td", "dd", "tr", "h2", "h3"]):
        value = _clean(node.get_text(" ", strip=True))
        if len(value) > 350 or not re.search(r"開催日|開催期間|日時|日程|イベント日|開催日時", value):
            continue
        m = re.search(r"(?:開催日時|開催期間|開催日|日時|日程|イベント日)[：:\s]*(.{4,130})", value)
        if not m:
            continue
        period = _period(m.group(1), published)
        if period:
            return period
    return None


def _publication_date(soup):
    node = soup.find("time", datetime=True)
    if node:
        m = re.search(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", node["datetime"])
        if m:
            return _date(*m.groups())
    for tag in soup.find_all("meta", attrs={"property": "article:published_time"}):
        m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", tag.get("content", ""))
        if m:
            return _date(*m.groups())
    return None


def collect_kinki_association(today):
    """Read linked articles and their event date fields, with page-local prefectures."""
    results, seen, checked = [], set(), 0
    for page_number in range(1, 4):
        url = KINKI if page_number == 1 else KINKI.rstrip("/") + f"/page/{page_number}/"
        try:
            listing = _get(url)
        except requests.RequestException as exc:
            print(f'近畿連絡会一覧 page={page_number} 取得失敗: {exc}')
            break
        page_candidates = 0
        for anchor in listing.select("a[href]"):
            title = _clean(anchor.get_text(" ", strip=True))
            match = re.search(r"[【〖][「\s]*道の駅\s*([^】〗」]+)[」]?([】〗])", title)
            if not match or any(w in title for w in SKIP):
                continue
            href = urljoin(url, anchor["href"])
            if urlparse(href).hostname not in ("www.kinki-michinoeki.com", "kinki-michinoeki.com"):
                continue
            if href in seen:
                continue
            seen.add(href)
            page_candidates += 1
            checked += 1
            container = anchor.find_parent(["article", "li", "div"]) or anchor.parent
            context = _clean(container.get_text(" ", strip=True))
            pref = next((p for p in ("滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県") if p in context), None)
            try:
                detail = _get(href)
            except requests.RequestException as exc:
                print(f"近畿詳細取得失敗: {href} ({exc})")
                continue
            if not pref:
                detail_text = _clean(detail.get_text(" ", strip=True))[:2500]
                pref = next((p for p in ("滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県") if p in detail_text), None)
            published_match = re.search(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})", context)
            published = _date(*published_match.groups()) if published_match else None
            period = _kinki_article_period(title, detail, published)
            if not pref or not period or period[1] < today.isoformat():
                continue
            road = _clean(match.group(1))
            if road and any(w in title + " " + _clean(detail.title.get_text(" ", strip=True) if detail.title else "") for w in EVENT_WORDS):
                results.append(_record(road, pref, title, period, href))
        if page_candidates == 0:
            break
    print(f"近畿連絡会: 詳細候補 {checked} / 採用 {len(results)} 件")
    return results


def collect_regional_associations(today):
    results = []
    for label, collector in (("東北", collect_tohoku_association),
                             ("近畿", collect_kinki_association)):
        try:
            results.extend(collector(today))
        except (requests.RequestException, ValueError, AttributeError) as exc:
            print(f"{label}連絡会の収集失敗（他地域は継続）: {exc}")
    return results

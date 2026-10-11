#!/usr/bin/env python3
"""Independent official-notice cross-check; not an automatic publisher.

Compares official regional source audits and a separate national association
notice index against published events. An unmatched URL is not proof that an
event is missing. Only manually reviewed, dated on-site evidence may count
toward a sample-specific recall estimate.
"""
import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from road_event_gap_monitor import _dated_headline_hint, _station_key, parse_app_station_master

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORT = DATA / "road_event_recall_audit.json"
DASHBOARD = ROOT / "docs" / "ROAD_EVENT_RECALL_DASHBOARD.md"
REVIEWS = DATA / "road_event_recall_reviews.json"
NATIONAL = "https://www.michi-no-eki.jp/notices"
JST = timezone(timedelta(hours=9))
EVENT_TERMS = ("祭", "まつり", "マルシェ", "イベント", "フェア", "フェス",
               "体験", "公演", "収穫", "夜市", "朝市", "スタンプラリー",
               "開催", "ワークショップ", "コンサート", "展示")


def _urlkey(value):
    p = urlparse(value or "")
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        return ""
    path = quote(unquote(p.path), safe="/-._~")
    return urlunparse(("https", p.hostname.lower(), path.rstrip("/") or "/",
                       "", p.query, ""))


def _titlekey(value):
    value = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"[\s・『』「」【】〖〗\[\]（）()!！、。:：]+", "", value)


def _station_from_title(title, master):
    """Only an unambiguous station inside a title's square brackets qualifies."""
    brackets = re.findall(r"(?:【([^】]{2,80})】|〖([^〗]{2,80})〗)",
                          unicodedata.normalize("NFKC", title or ""))
    brackets = [left or right for left, right in brackets]
    if not brackets:
        return None
    matches = {}
    for st in master.get("stations", []):
        name = _station_key(st["prefecture"], st["roadName"])[1]
        name = name.replace("「", "").replace("」", "")
        if len(name) < 2:
            continue
        for part in brackets:
            label = _station_key(st["prefecture"], part)[1]
            label = label.replace("「", "").replace("」", "")
            if name == label or (len(name) >= 3 and name in label
                                 and "道の駅" in part):
                matches[(st["prefecture"], st["roadName"])] = st
                break
    return next(iter(matches.values())) if len(matches) == 1 else None


def parse_national_notices(html, limit=35):
    """Accept only actual national-association notice detail links."""
    found, seen = [], set()
    for a in BeautifulSoup(html, "html.parser").select("a[href]"):
        url = _urlkey(urljoin(NATIONAL, a.get("href", "")))
        parsed = urlparse(url)
        if (parsed.hostname not in ("www.michi-no-eki.jp", "michi-no-eki.jp")
                or not re.fullmatch(r"/notices/views/[0-9]+", parsed.path)
                or url in seen):
            continue
        title = " ".join(a.get_text(" ", strip=True).split())
        if not title:
            continue
        found.append({"title": title[:350], "url": url})
        seen.add(url)
        if len(found) >= limit:
            break
    return found


def fetch_national(fetch=None):
    """One HTTP request; a transient failure does not block event collection."""
    if fetch is None:
        def fetch(url):
            response = requests.get(url, timeout=12, headers={
                "User-Agent": "MichinotochuRoadEventBot/1.4 (official notice cross-check)"})
            response.raise_for_status()
            return response.text
    try:
        candidates = parse_national_notices(fetch(NATIONAL))
        return {"name": "全国道の駅連絡会", "url": NATIONAL,
                "reachable": True, "candidateCount": len(candidates),
                "candidates": candidates, "error": ""}
    except (requests.RequestException, OSError, ValueError, TypeError) as exc:
        return {"name": "全国道の駅連絡会", "url": NATIONAL,
                "reachable": False, "candidateCount": 0,
                "candidates": [], "error": f"{type(exc).__name__}: {str(exc)[:160]}"}


def _iso(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def reviewed_sample(ledger, published, today=None):
    """Only verified, individually documented, in-scope notices enter the rate.

    The published event feed drops events after their end date. A verified
    historic event must not become a *new miss* merely because it expired.
    """
    if ledger.get("schemaVersion") != 1:
        raise ValueError("Unrecognized independent review ledger version")
    results, seen = [], set()
    as_of = _iso(today) if today is not None else None
    if today is not None and as_of is None:
        raise ValueError("Invalid evaluation date")
    for item in ledger.get("reviews", []):
        decision = item.get("decision")
        url = _urlkey(item.get("officialUrl"))
        if (decision not in ("confirmed_on_site", "not_station_event")
                or not url or not _iso(item.get("reviewedOn"))):
            raise ValueError("Review requires decision, HTTPS URL and ISO review date")
        key = (url, item.get("title"), item.get("startDate"))
        if key in seen:
            raise ValueError("Duplicate reviewed event")
        seen.add(key)
        if decision == "confirmed_on_site":
            start, end = _iso(item.get("startDate")), _iso(item.get("endDate"))
            if (not start or not end or end < start or
                    not all(item.get(k) for k in
                            ("prefecture", "roadName", "title", "dateEvidence", "venueEvidence"))):
                raise ValueError("Positive review lacks independently verified venue or date")
            station = _station_key(item["prefecture"], item["roadName"])
            if as_of is not None and end < as_of:
                results.append({**item, "matchStatus": "expired_outside_live_feed",
                                "inCurrentSample": False})
                continue
            hits = [event for event in published
                    if _station_key(event.get("prefecture"), event.get("roadName")) == station
                    and _iso(event.get("startDate")) and _iso(event.get("endDate"))
                    and _iso(event["startDate"]) <= end
                    and start <= _iso(event["endDate"])
                    and SequenceMatcher(None, _titlekey(event.get("title")),
                                        _titlekey(item["title"])).ratio() >= .83]
            status = "found_in_feed" if hits else "verified_notice_not_found_in_feed"
        else:
            if not item.get("reason"):
                raise ValueError("Negative review requires an exclusion reason")
            status = "excluded_nonstation_event"
        results.append({**item, "matchStatus": status,
                        "inCurrentSample": decision == "confirmed_on_site"})
    historical_positives = [x for x in results if x["decision"] == "confirmed_on_site"]
    positives = [x for x in historical_positives if x["inCurrentSample"]]
    hits = sum(x["matchStatus"] == "found_in_feed" for x in positives)
    return {"reviews": results, "reviewed": len(results),
            "positiveOnSite": len(positives),
            "historicalPositiveReviews": len(historical_positives),
            "expiredPositiveReviews": len(historical_positives) - len(positives),
            "found": hits,
            "notFound": len(positives) - hits,
            "rateWithinReviewedSample": round(hits / len(positives), 3)
            if positives else None,
            "limitations": "Selected human-reviewed examples only; NOT national event recall."}


def notice_review_priority(title, date_hint, today):
    """Queue ordering only; never decides event dates or publication.

    Old-year text and mismatched weekday are *hints*, not evidence that
    a notice has expired. Current-year dates can also be publication dates.
    """
    value = unicodedata.normalize("NFKC", title or "")
    if date_hint == "future_schedule_hint":
        return "future_schedule_hint"
    check_day = _iso(today)
    if check_day is None:
        raise ValueError("Invalid audit date")
    years = [int(y) for y in re.findall(r"(?<![0-9])20[0-9]{2}(?![0-9])", value)]
    years.extend(2018 + int(y) for y in
                 re.findall(r"令和\s*([0-9]{1,2})年", value))
    if years and max(years) < check_day.year:
        return "older_year_mentioned"
    # An unyeared '10月13日(日)' may refer to an older notice. A weekday
    # mismatch is a reason to CHECK the year, never to exclude the item.
    weekday_ids = {"月": 0, "火": 1, "水": 2, "木": 3,
                   "金": 4, "土": 5, "日": 6}
    for m in re.finditer(
            r"(?<![0-9])([0-9]{1,2})月\s*([0-9]{1,2})日"
            r"\s*[\(（]([月火水木金土日])[\)）]", value):
        try:
            stated = date(check_day.year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return "date_in_title_needs_verification"
        if stated.weekday() != weekday_ids[m.group(3)]:
            return "weekday_year_mismatch_check"
    if date_hint == "past_schedule_hint":
        return "past_schedule_hint"
    return "date_and_venue_verification_needed"


def make_report(regional, national, master, published, ledger, today):
    sources = [{"name": x.get("region"), "url": x.get("url"),
                "reachable": x.get("reachable"), "candidates": x.get("candidates", [])}
               for x in regional.get("sources", [])]
    sources.append(national)
    known = {}
    for event in published:
        known.setdefault(_urlkey(event.get("url")), []).append(event)
    candidates, seen = [], set()
    for src in sources:
        for item in src.get("candidates", []):
            url = _urlkey(item.get("url"))
            title = item.get("title", "")
            if not url or url in seen or not any(w in title for w in EVENT_TERMS):
                continue
            # Regional homepage audit also surfaces navigation pages; do not
            # mistake an event category or index for an individual notice.
            route = urlparse(url).path.rstrip("/")
            if (title in ("イベント", "イベント情報", "お知らせ", "催し") or
                    "/category/" in route or route in (
                        "/events", "/news", "/notices", "/news-tag/event")):
                continue
            seen.add(url)
            station = _station_from_title(title, master)
            if url in known:
                titles = [event.get("title", "") for event in known[url]]
                matched = any(
                    _titlekey(title) in _titlekey(t) or
                    _titlekey(t) in _titlekey(title) or
                    SequenceMatcher(None, _titlekey(title),
                                    _titlekey(t)).ratio() >= .75
                    for t in titles if _titlekey(t))
                status = ("published_same_official_url" if matched else
                          "same_official_url_title_needs_review")
                overlaps = [] if matched else [x["url"] for x in known[url][:3]]
            elif station is None:
                status, overlaps = "station_not_unambiguously_identified", []
            else:
                station_events = [event for event in published
                    if _station_key(event.get("prefecture"), event.get("roadName")) ==
                       _station_key(station["prefecture"], station["roadName"])]
                overlaps = [e["url"] for e in station_events
                    if SequenceMatcher(None, _titlekey(title),
                        _titlekey(e.get("title"))).ratio() >= .80][:3]
                status = ("possible_same_event_other_url" if overlaps
                          else "unmatched_official_notice")
            candidates.append({
                "source": src.get("name", ""), "title": title[:240], "url": url,
                "prefecture": station["prefecture"] if station else "",
                "roadName": station["roadName"] if station else "",
                "status": status, "possibleOverlapUrls": overlaps,
                "headlineDateHint": _dated_headline_hint(title, today),
                "reviewPriority": notice_review_priority(
                    title, _dated_headline_hint(title, today), today),
                "evidenceStatus": "listing_only_not_date_or_venue_verified"})
    kinds = ("unmatched_official_notice", "same_official_url_title_needs_review",
             "possible_same_event_other_url", "station_not_unambiguously_identified",
             "published_same_official_url")
    ranks = {key: index for index, key in enumerate(kinds)}
    priority_order = {
        "future_schedule_hint": 0,
        "date_and_venue_verification_needed": 1,
        "date_in_title_needs_verification": 2,
        "weekday_year_mismatch_check": 3,
        "past_schedule_hint": 4,
        "older_year_mentioned": 5,
    }
    candidates.sort(key=lambda x: (
        priority_order[x["reviewPriority"]], ranks[x["status"]],
        x["source"], x["url"]))
    counts = {kind: sum(x["status"] == kind for x in candidates) for kind in kinds}
    # Do not subtract stale-looking articles from unresolved status totals.
    # This is review-queue triage, not proof of event completion or omission.
    review_kinds = ("unmatched_official_notice",
                    "same_official_url_title_needs_review")
    review_queue = [x for x in candidates if x["status"] in review_kinds]
    triage_counts = {kind: sum(x["reviewPriority"] == kind for x in review_queue)
                     for kind in priority_order}
    sample = reviewed_sample(ledger, published, today=today)
    return {
        "schemaVersion": 1, "checkedOn": today,
        "summary": {
            "officialSources": len(sources),
            "reachableSources": sum(x.get("reachable") is True for x in sources),
            "announcementsCompared": len(candidates),
            "statuses": counts,
            "candidatesForManualReview": (counts["unmatched_official_notice"] +
                                          counts["same_official_url_title_needs_review"]),
            "sampleVerifiedOnSite": sample["positiveOnSite"],
            "sampleExpiredExcluded": sample["expiredPositiveReviews"],
            "sampleFound": sample["found"], "sampleNotFound": sample["notFound"],
            "sampleDiscoveryRate": sample["rateWithinReviewedSample"],
            "reviewPriorityCounts": triage_counts,
        },
        "limitations": {
            "coverage": "Regional homepage samples and a bounded national first-page notice index only.",
            "unmatched": "An unmatched URL/title is NOT proof of a missing station event.",
            "measurement": "A manually reviewed non-random sample does NOT measure national recall."},
        "sources": [{k: x.get(k) for k in ("name", "url", "reachable", "error")}
                    for x in sources],
        "candidates": candidates[:150], "reviewedSample": sample}


def render_dashboard(report):
    s = report["summary"]
    out = ["# 道の駅イベント・独立公式告知との照合",
           "", "監査日（日本時間）: **{}**".format(report["checkedOn"]),
           "", "**別の公式情報源でイベント収集漏れの可能性を検査する監査です。**",
           "URL不一致は取りこぼし確定ではありません。開催日と駅構内会場の独立確認が必要です。",
           "", "## 公式告知の照合結果", "",
           "| 指標 | 件数 |", "|---|---:|",
           "| 監査に含めた公式情報源 | {} |".format(s["officialSources"]),
           "| 取得できた公式情報源 | {} |".format(s["reachableSources"]),
           "| 公式告知見出しの比較数 | {} |".format(s["announcementsCompared"]),
           "| 公式記事URLが公開データと一致 | {} |".format(
               s["statuses"]["published_same_official_url"]),
           "| 対応する公開イベント未発見（要確認） | {} |".format(
               s["statuses"]["unmatched_official_notice"]),
           "| 同じ公式URLだが題名不一致（要確認） | {} |".format(
               s["statuses"]["same_official_url_title_needs_review"]),
           "| 別URLの同一催しの可能性 | {} |".format(
               s["statuses"]["possible_same_event_other_url"]),
           "| 道の駅名を特定できない見出し | {} |".format(
               s["statuses"]["station_not_unambiguously_identified"]),
           "", "## 要確認候補の優先順位（登録可否の判定ではありません）", "",
           "| 確認の手掛かり | 件数 |", "|---|---:|",
           "| 開催予定日の手掛かりあり | {} |".format(
               s["reviewPriorityCounts"]["future_schedule_hint"]),
           "| 日付・会場の個別確認が必要 | {} |".format(
               s["reviewPriorityCounts"]["date_and_venue_verification_needed"]),
           "| 記載日付の確認が必要 | {} |".format(
               s["reviewPriorityCounts"]["date_in_title_needs_verification"]),
           "| 曜日と今年の日付が不一致（年要確認） | {} |".format(
               s["reviewPriorityCounts"]["weekday_year_mismatch_check"]),
           "| 過去の日程を示唆 | {} |".format(
               s["reviewPriorityCounts"]["past_schedule_hint"]),
           "| 前年以前の年表記あり | {} |".format(
               s["reviewPriorityCounts"]["older_year_mentioned"]),
           "", "この分類は見出しだけから作った作業順です。過年度・曜日不一致でも削除や自動不採用はせず、公式本文で確認します。",
           "", "## 独立に確認した標本（全国の網羅率ではありません）", "",
           "- 開催日・駅会場を個別確認したイベント: {}件".format(s["sampleVerifiedOnSite"]),
           "- 公開イベントと照合できた件数: {}件".format(s["sampleFound"]),
           "- 終了日の経過で現行標本から除外した検証済みイベント: {}件".format(
               s["sampleExpiredExcluded"]),
           "- 公開イベントと照合できない件数: {}件".format(s["sampleNotFound"]),
           ("- 標本内の発見率: {:.1%}".format(s["sampleDiscoveryRate"])
            if s["sampleDiscoveryRate"] is not None
            else "- 標本内の発見率: 未算出（確認済みの正例なし）"),
           "", "## 対応する公開イベントが見つからなかった公式告知", "",
           "| 優先判定 | 情報源 | 県・駅 | 見出し | 公式URL |",
           "|---|---|---|---|---|"]
    missing = [x for x in report["candidates"]
               if x["status"] in ("unmatched_official_notice",
                                   "same_official_url_title_needs_review")]
    for item in missing[:25]:
        title = item["title"].replace("|", "｜").replace("\n", " ")[:100]
        url = item["url"].replace("(", "%28").replace(")", "%29")
        out.append("| {} | {} | {} {} | {} | [原文]({}) |".format(
            item["reviewPriority"], item["source"],
            item["prefecture"], item["roadName"], title, url))
    if not missing:
        out.append("| ― | ― | ― | 現在の対象記事に候補なし | ― |")
    out.extend(["", "## 判定ルール", "",
      "- イベント本文の日時・会場確認をしていない候補は勝手に登録しません。",
      "- 別の公式URLで同じ催しが登録済みの可能性も、上の候補には残り得ます。",
      "- 人が公式本文で確認した証拠だけをレビュー台帳に登録した場合に限り、標本内の発見率を計算。",
      "- この標本はランダム抽出ではなく、全国の真のイベント発見率の推定には使えません。",
      "- 現在の公開フィードから終了済み催事が消えても、過去の捕捉漏れとしては数えません。",
      "", "[監査JSON](../data/road_event_recall_audit.json) ／ "
         "[収集漏れ監査](ROAD_EVENT_GAP_DASHBOARD.md)", ""])
    return "\n".join(out)


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    today = datetime.now(JST).date().isoformat()
    station_master = parse_app_station_master(
        (DATA / "app_data.js").read_text(encoding="utf-8"))
    national = fetch_national()
    report = make_report(
        _read(DATA / "road_event_sources_report.json"), national,
        station_master, _read(DATA / "road_events.json")["events"],
        _read(REVIEWS), today)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if not REPORT.exists() or REPORT.read_text(encoding="utf-8") != rendered:
        REPORT.write_text(rendered, encoding="utf-8")
    dashboard = render_dashboard(report)
    if not DASHBOARD.exists() or DASHBOARD.read_text(encoding="utf-8") != dashboard:
        DASHBOARD.write_text(dashboard, encoding="utf-8")
    s = report["summary"]
    print("独立公式告知照合: 記事 {}件 / 未一致候補 {}件 / "
          "人手確認済みイベント {}件 / 標本内発見率 {}".format(
              s["announcementsCompared"], s["candidatesForManualReview"],
              s["sampleVerifiedOnSite"],
              "未算出" if s["sampleDiscoveryRate"] is None
              else "{:.1%}".format(s["sampleDiscoveryRate"])))
    if not national["reachable"]:
        print("::warning title=Independent national official notice::{}".format(
            national["error"].replace("\n", " ")[:150]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

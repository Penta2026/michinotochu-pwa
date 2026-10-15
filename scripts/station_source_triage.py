"""Build a nationwide, read-only shortlist from previously visited station websites.

This is a pre-onboarding review queue only. Neither a station name mention nor
an event-like anchor proves official ownership, event occurrence or venue.
Absolutely no changes to the live discovery-source registry or event JSON.
"""
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from station_coverage_registry import station_key

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = DATA / "station_source_triage.json"
DASHBOARD = ROOT / "docs" / "STATION_SOURCE_TRIAGE_DASHBOARD.md"


def _same_host_event_links(home, links):
    host = urlsplit(home).hostname
    clean = []
    for raw in links:
        if not isinstance(raw, str):
            continue
        candidate = urljoin(home, raw)
        try:
            p = urlsplit(candidate)
            if (p.scheme != "https" or p.hostname != host or
                    p.username or p.password or p.port is not None):
                continue
        except ValueError:
            continue
        candidate = p._replace(fragment="").geturl()
        if candidate not in clean:
            clean.append(candidate)
    return clean[:8]


def build(queue, audit, configured, coverage, *, limit=50):
    if not 1 <= limit <= 50:
        raise ValueError("Review shortlist limited to 50 stations")
    known = {
        station_key(s["prefecture"], s["roadName"])
        for s in configured.get("sources", []) if s.get("enabled", True)
    }
    zeros = {
        p["prefecture"] for p in coverage.get("prefectures", [])
        if p.get("eventCount") == 0
    }
    stations = {x["id"]: x for x in queue["stations"]}
    if len(stations) != len(queue["stations"]):
        raise ValueError("Duplicate station IDs in master review queue")
    reviewed = {}
    for item in audit.get("results", []):
        station = stations.get(item.get("stationId"))
        if station is None or station.get("directoryInspectionState") != "checked":
            continue
        current = {
            x["url"] for x in station.get("candidates", [])
            if x.get("kind") == "station_or_partner_site_unverified"
        }
        if item.get("url") not in current:
            continue
        # Repeated attempts use the latest recorded result for this same URL.
        reviewed[(station["id"], item["url"])] = item
    rows = []
    for (station_id, home), item in reviewed.items():
        station = stations[station_id]
        key = station_key(station["prefecture"], station["roadName"])
        if key in known:
            continue
        if item.get("status") != "identity_mentioned_unverified" or not item.get("stationNameMentioned"):
            continue
        hints = _same_host_event_links(home, item.get("eventLinkHints") or [])
        rows.append({
            "stationId": station_id,
            "prefecture": station["prefecture"],
            "roadName": station["roadName"],
            "websiteUrl": home,
            "eventLinkHints": hints,
            "discoveryTier": "linked_notice_candidate" if hints else "station_name_only",
            "zeroCurrentEventPrefecture": station["prefecture"] in zeros,
            "officialSiteOwnershipVerified": False,
            "eventListingVerified": False,
            "readyForPublishing": False,
            "nextAction": "Verify official ownership, dated individual notices, and on-site event venue before source onboarding",
        })
    rows.sort(key=lambda item: (
        not item["zeroCurrentEventPrefecture"],
        item["discoveryTier"] != "linked_notice_candidate",
        -len(item["eventLinkHints"]),
        item["stationId"], item["websiteUrl"]))
    status = Counter(x.get("status", "unknown") for x in reviewed.values())
    selected = rows[:limit]
    return {
        "schemaVersion": 1,
        "basisCheckedAt": audit.get("checkedAt", ""),
        "masterStations": len(stations),
        "configuredStationCount": len(known),
        "inspectedStationWebsiteUrls": len(reviewed),
        "reviewStatuses": dict(sorted(status.items())),
        "potentialStationSites": len(rows),
        "potentialEventListingSites": sum(bool(x["eventLinkHints"]) for x in rows),
        "shortlisted": len(selected),
        "remainingPotentialSites": max(0, len(rows) - len(selected)),
        "shortlist": selected,
        "limitations": "Automated URL hints are not verified website ownership, events, dates or venues. No events or source configurations were published.",
    }


def render_markdown(payload):
    lines = [
        "# 道の駅・全国公式収集先の一次調査候補",
        "",
        "※ **公式サイト確定・イベント登録の台帳ではない**。駅名がページ内に現れた未確認サイト候補を整理したもの。",
        "",
        f"- 全国道の駅台帳: {payload['masterStations']}駅",
        f"- 調査済みホームページ候補URL: {payload['inspectedStationWebsiteUrls']}件",
        f"- 駅名の現れたサイト候補: {payload['potentialStationSites']}件",
        f"- イベントらしいリンクを持つ候補: {payload['potentialEventListingSites']}件",
        f"- 今回の優先レビュー枠: {payload['shortlisted']}件 / 残り候補 {payload['remainingPotentialSites']}件",
        "",
        "| 駅ID | 県 | 道の駅 | 優先理由 | 催しリンク候補数 | 調査するURL |",
        "|---|---|---|---|---:|---|",
    ]
    for item in payload["shortlist"]:
        priority = ("掲載0県・" if item["zeroCurrentEventPrefecture"] else "") + (
            "イベントらしいリンク" if item["eventLinkHints"] else "駅名一致のみ")
        url = item["eventLinkHints"][0] if item["eventLinkHints"] else item["websiteUrl"]
        lines.append("| {} | {} | {} | {} | {} | {} |".format(
            item["stationId"], item["prefecture"], item["roadName"].replace("|", "｜"),
            priority, len(item["eventLinkHints"]), url.replace("|", "%7C")))
    lines += [
        "",
        "## 次に確認すること",
        "",
        "1. URLが該当道の駅の公式サイト／正当な運営主体のものか一次情報で確認する。",
        "2. 催し一覧から個別記事を見つけ、本文の年付き開催日・駅構内の会場を照合する。",
        "3. HTMLの構造ごとに共通パーサを使用して20～50駅単位のオンボーディング用テストを作る。",
        "4. テストに通った収集先だけ別途明示的に有効化し、公開イベントは通常の品質監査を通す。",
        "",
        "サイトに駅名があっても、写真やバナーの日付を推定したり、駅外イベントを登録したりしない。",
        "",
    ]
    return "\n".join(lines)


def main():
    queue = json.loads((DATA / "station_website_review_queue.json").read_text(encoding="utf-8"))
    if len(queue.get("stations", [])) != 1234:
        raise ValueError("National station review queue is incomplete")
    audit_path = DATA / "station_website_batch_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
    configured = json.loads((DATA / "station_event_discovery_sources.json").read_text(encoding="utf-8"))
    coverage = json.loads((DATA / "prefecture_event_coverage.json").read_text(encoding="utf-8"))
    result = build(queue, audit, configured, coverage)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DASHBOARD.write_text(render_markdown(result), encoding="utf-8")
    print("全国公式URL候補: 審査用上位 {}/50件, イベントリンク候補を持つサイト {}/{}件。公開データ変更なし".format(
        result["shortlisted"], result["potentialEventListingSites"], result["potentialStationSites"]))


if __name__ == "__main__":
    main()

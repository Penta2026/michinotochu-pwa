"""Track a 10–12-day first-pass target without calling unknown stations verified."""
import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from math import ceil
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
DASHBOARD = DATA.parent / "docs" / "STATION_12_DAY_BOOTSTRAP_STATUS.md"
TARGET_STATIONS = 1234
DAILY_DIRECTORY_TARGET = 96
DAILY_WEBSITE_TARGET = 120


def render(directory, batch, probe, published, *, today):
    dir_rows = directory.get("stations", [])
    ids = {s["id"] for s in dir_rows}
    if len(dir_rows) != len(ids) or len(ids) > TARGET_STATIONS:
        raise ValueError("National directory IDs mismatch")
    detail_ok = sum(x.get("directoryCheckStatus") == "directory_identity_checked"
                    for x in dir_rows)
    visits = {(r.get("stationId"), r.get("url")) for r in batch.get("results", [])}
    touched_stations = {code for code, url in visits if code and url}
    probe_sites = {x["stationId"] for x in probe.get("stations", [])}
    known_events = published.get("events", [])
    eligible = max(0, TARGET_STATIONS - len(ids))
    days = ceil(eligible / DAILY_DIRECTORY_TARGET)
    reason = directory.get("lastDirectoryError", "")
    report = [
        "# 全国1,234駅・10〜12日集中収集の進捗",
        "",
        f"更新日: {today.isoformat()}（日本時間）",
        "",
        "> この数値は**実測の調査進捗**。名簿を調べた駅と、イベントを実際に掲載できた駅は別。",
        "",
        "| 段階 | 実測 | 目標・制限 |",
        "|---|---:|---|",
        f"| 全国道の駅の台帳 | {TARGET_STATIONS}駅 | 全駅を追跡 |",
        f"| 公式名簿で調査した駅 | {len(ids)}駅 | 96駅/日（最大） |",
        f"| 公式名簿と駅名が照合した駅 | {detail_ok}駅 | 正式なサイト所有者確認とは別 |",
        f"| 名簿未調査 | {eligible}駅 | 理論上、残り約{days}回の正常な日次実行 |",
        f"| ホームページ候補にアクセスした駅 | {len(touched_stations)}駅 | 120サイト/日（最大） |",
        f"| 厳密な開催情報の検査対象となった駅 | {len(probe_sites)}駅 | 60駅/日（最大） |",
        f"| 現在公開中の全国イベント | {len(known_events)}件 | 期日・会場・公式根拠が必要 |",
        "",
        "## 運用目標",
        "",
        "- 初回10〜12日: 全国公式名簿を一巡、公式サイト候補を一次調査し、確認できた開催情報を収集する。",
        "- 13日目以降: 未解決サイトへの追加調査と、確認済み告知元の定期再確認を続ける。",
        "- 日次06:00 JST: 厳密検証に通過したイベント候補を既存の全国イベントJSONに統合する。",
        "- ユーザーはPWAの『イベント情報を更新』で、端末に最新の全国JSONを保存する。",
        "",
        "## 注意・障害",
        "",
        "名簿の確認完了は『全駅のイベントが集まった』という意味ではない。",
        "候補URL・本文未確認・駅構内会場未確認はイベント公開件数へ算入しない。",
        "更新のない道の駅、イベント未掲載駅、robots規則による制限、日時不明の告知は未確認のまま残す。",
    ]
    if reason:
        report.extend(["", "**直近の公式名簿障害:** " + reason.replace("|", "｜"),
                       "保存済みカーソルを維持。復旧後に再開し、残日数の計算は延びる。"])
    else:
        report.extend(["", "直近の公式名簿障害: 記録なし。"])
    report += ["", "## サイト調査の内訳", "",
               "| 結果 | 監査記録数 |", "|---|---:|"]
    states = Counter(r.get("status", "unknown") for r in batch.get("results", []))
    report += [f"| {k.replace('|','｜')} | {v} |" for k,v in sorted(states.items())]
    return "\n".join(report) + "\n"


def main():
    def read(name):
        p = DATA / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    text = render(read("station_official_directory_candidates.json"),
                  read("station_website_batch_audit.json"),
                  read("station_national_event_probe_audit.json"),
                  read("road_events.json"), today=datetime.now(timezone(timedelta(hours=9))).date())
    DASHBOARD.write_text(text, encoding="utf-8")
    print("Nationwide bootstrap dashboard: " + str(DASHBOARD))


if __name__ == "__main__":
    main()

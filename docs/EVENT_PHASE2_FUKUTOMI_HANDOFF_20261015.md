# 道の途中。イベント収集 Phase 2 福富公式サイト対応 引継ぎ（2026-10-15）

## 変更履歴
- data/station_event_discovery_sources.json: 広島県「湖畔の里福富」の公式お知らせ一覧を登録。既存収集フローで公式記事を取得して、記事内の日付・会場を検証する。掲載日の流用は禁止。
- scripts/test_fukutomi_event_discovery.py: 公式一覧リンクの発見、明示的な開催日+会場の採用、告知日の混同防止、別会場の拒否についてオフライン回帰テストを追加。
- .github/workflows/road-events.yml: 回帰テストを日次ジョブに追加。
- scripts/station_lightwatch.py はPhase 1からそのまま維持。既存イベント収集も維持。

## 公式資料
- 公式お知らせ一覧 https://kohannosato.co.jp/news/
- 2026年9月23日「レトロカーフェスタ2026 エントリー開始！」の掲載を確認
- 2026年11月3日の開催情報は外部日程表等でも確認。**実際のイベント本文が自動抽出で採用されるかは GitHub Actions 実行ログ・収集監査で要確認**。機械処理で日付や会場が検証できなければ未掲載のままが正しい。

## 動作確認手順
1. GitHub Actions > 道の駅イベント情報（全国・地域別） > Run workflow を実行。
2. 緑のチェックを確認。赤ならテストまたは収集ログを確認して修正。
3. data/station_event_discovery_audit.json の id=hiroshima_fukutomi を確認（candidates/checked/accepted/reasons/listingError）。
4. data/road_events.json で roadName=湖畔の里福富、startDate=2026-11-03 が採用されているか確認。
5. 未採用の場合、公式記事のHTML構造・日時表記・掲載タイトルの拒否理由を元に調整。根拠のない固定日付の挿入はしない。

## 課題
- 全1,234駅のうち個別収集先はまだ僅か。広島県から段階的に情報源を検証して増やす。
- 軽量巡回（変更検出）と記事の検証・登録は別処理。単なるページ差分をイベント掲載しない。
- 収集先ごとの robots.txt、規約、通信負荷を尊重する。
- GitHub Actions正常完了は全国網羅を保証しない。

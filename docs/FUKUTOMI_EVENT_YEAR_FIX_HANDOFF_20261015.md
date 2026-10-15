# 道の途中。福富イベント日付補完 Phase 2 引継ぎ（2026-10-15）

## 背景・原因
GitHub Actions の福富公式サイト監査で、記事8件、レトロカーフェスタ2026は undated で除外。
記事本文「11月3日(火・祝)、道の駅湖畔の里福富に...開催いたします」には開催月日と会場が明示。
記事のイベント名には2026が明記。開催年月日の結合が既存解析でできていなかった。

## 変更
- scripts/station_discovery_engine.py: _event_title_year_month_day ヘルパーを追加。イベントタイトルの単一年と、同一記事のイベント文脈内の単一の月日があり、今日以降に限り開催日候補を補完。
- data/station_event_discovery_sources.json: hiroshima_fukutomi に allowEventTitleYearForArticleMonthDay=true を設定。他の駅では無効。
- scripts/test_fukutomi_event_discovery.py: 福富記事の年+月日と、複数候補日の誤採用を避ける回帰テストを追加。既存の発行日誤用・別会場テストも残す。
- 既存の全国・地域イベント収集と掲載審査は変更していない。

## 確認
GitHub Actions > 道の駅イベント情報（全国・地域別） > Run workflow
https://github.com/Penta2026/michinotochu-pwa/actions/workflows/road-events.yml

正常終了後、data/station_event_discovery_audit.json 内 id=hiroshima_fukutomi の accepted と examples を確認。
data/road_events.json 内 roadName=湖畔の里福富、startDate=endDate=2026-11-03 があるか確認。
まだランタイム結果は未確認。失敗した場合は最新アクションログと rejectedExamples を調査。
GitHub緑チェックのみでは掲載確認にならないことに注意。

## 次段階
広島県内の情報源の追加と全国のカバレッジ拡大。軽量巡回で更新検知したページの新着記事解析へ進む。
期限・会場・重複を保守的に扱い、推測した掲載をしない。

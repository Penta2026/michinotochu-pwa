# 道の途中。広島県駅別情報源拡大 第2駅 引継ぎ（2026-10-15）

## 実施
- 公式サイトを確認した「道の駅 西条のん太の酒蔵」を駅別収集先へ追加。
- data/station_event_discovery_sources.json: hiroshima_nonta、イベント一覧 https://www.nonta-sakagura.com/news_category/cate01
- scripts/station_discovery_engine.py: イベント名の単一開催年と、記事内「11月28日（土）29日（日）」など同月の連続2日をセットで検証。対象の駅ルールでのみ有効。
- scripts/test_nonta_two_day_events.py: 2日間の抽出、年不明・離れた日・別会場の拒否をオフラインテスト。
- .github/workflows/road-events.yml: テストを追加。

## 収集対象イベント
公式告知「ぶちうまい！東広島お米フェス2026を開催いたします。」
2026年11月28日〜29日 10:00〜15:00 道の駅 西条のん太の酒蔵。
公式告知は2026年9月19日掲載。自治体の関連案内も同じ日時と会場を掲載。

## 次の実行と検証
https://github.com/Penta2026/michinotochu-pwa/actions/workflows/road-events.yml
Run workflow を実行し、テストと収集が緑になったか確認。
次に data/station_event_discovery_audit.json の hiroshima_nonta で accepted / reasons / listingError を検証。
data/road_events.json の 西条のん太の酒蔵、startDate=2026-11-28, endDate=2026-11-29 を確認する。
現時点で GitHub Actions の稼働・自動登録は未検証。

## 注意
- 個別URLや記事構造が想定と異なる場合は診断を見て修正する。
- 暫定で他の広島20駅に未確認のURLを割り当てない。
- 2日開催補完を無条件で全国に適用しない。
- 今後は広島の他駅にも一次情報源を確認したうえで追加し、全国1,234駅の収集率を高める。

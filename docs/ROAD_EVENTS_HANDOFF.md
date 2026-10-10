# 「道の途中。」道の駅イベント自動収集 — 進捗・引継ぎ

更新基準: **2026-10-10**（GitHubの現行データを確認した時点）  
リポジトリ: `Penta2026/michinotochu-pwa` / `main`  
ワークフロー: [road-events.yml](../.github/workflows/road-events.yml)  
イベント: [data/road_events.json](../data/road_events.json)  
**県別最新レポート**: [data/prefecture_event_coverage.json](../data/prefecture_event_coverage.json)（次のGitHub Actions成功時に初めて作成）

## 直近の状態（2026-10-10の実測）

- **公開イベント50件／イベント登録実績26都道県／実績なし21都府県**。
- 9地域の公式トップページの接続監査あり。**トップ接続成功は、その地域内すべての県でイベント収集が成功した意味ではない**。
- 北陸はSeleniumによるJS描画取得を実装。5件収集、表示日`dc`の違いによる重複は記事`article`番号で解消。
- 九州・沖縄は8県で各1つの情報源を設定。福岡（くるめ）、沖縄（かでな）、佐賀（しろいし）、大分（耶馬トピア）で計4件のイベント登録実績。他の4県は現時点0件。
- 品質監査: 重複候補0件、開催日訂正0件、**未再確認1件**。北海道「たきかわ・大収穫祭」（10/17〜18）は保持されているが、最新収集では未再確認。消去や開催中止とみなさないこと。
- 注意: 50件は「現在公開しているイベントレコード」数。実際の全イベント網羅件数ではない。

## 県別の空白21県（現行データの実測）

| 報告地域 | イベント未登録県 | 県数 |
|---|---|---:|
| 北海道 | なし | 0 |
| 東北 | 岩手・山形・福島 | 3 |
| 関東 | 茨城・栃木・群馬・千葉・東京・神奈川 | 6 |
| 北陸 | なし | 0 |
| 中部 | 静岡 | 1 |
| 近畿 | 福井・京都・大阪・奈良・和歌山 | 5 |
| 中国 | 山口 | 1 |
| 四国 | 愛媛 | 1 |
| 九州・沖縄 | 長崎・熊本・宮崎・鹿児島 | 4 |
| **合計** | **21都府県** | **21** |

※分類はこの監査用の9地域区分。県別の地理区分と公式連絡会の所管は必ずしも同一ではない。

## 今回実装した「47県進捗見える化」 （次回Run workflowで検証）

- `scripts/prefecture_event_coverage.py` : イベントJSON、地域トップ監査、品質監査、九州8県の固定情報源設定を突き合わせて**47県全部**について状態を記録する。
- `scripts/test_prefecture_event_coverage.py` : 全47県、9地域、重複なし、対象サイトとの区別、未再確認、異常な県名を検査。
- `.github/workflows/road-events.yml` : 本収集の終了後に県別監査を実行し `data/prefecture_event_coverage.json` をコミット対象に加えた。
- `prefectures[].state` : `events_observed` / `targeted_feed_no_registered_events` / `no_registered_events` / `needs_reconfirmation`。**登録がないことは開催がないことを意味しない**。
- `targetedStationFeeds` : 九州・沖縄の8県で明示的に設定された駅情報源を列挙。ここに掲載されない別地域の収集器の存在を否定する指標ではない。
- `regionalHomepageReachable` : 公式地域トップに到達したかのみ。実際のイベント収集成否と切り離す。

## 未解決・優先順位

1. **北海道・たきかわの未再確認1件**。公式記事の継続掲載、収集経路、取得エラーを確認。保持中のデータを不用意に消さない。
2. **関東の未登録6都県／近畿の未登録5府県**。駅別公式イベント一覧を発掘し、日付の誤認を防ぐアダプタを追加。登録済み県も全道の駅カバー済みとはみなさない。
3. **九州未登録4県（長崎・熊本・宮崎・鹿児島）**。公式記事の候補は取得成功したが日付未確定。各県の `data/kyushu_six_prefectures_audit.json` に候補・失敗理由あり。熊本「すいかの里植木」は記事のタイトル・日付欄解析を重点調査。
4. 東北3県、中部静岡、中国山口、四国愛媛を順次確認。
5. 診断レポートの統一と、未登録県に対する駅別情報源の探索を継続する。

## 実行手順・引継ぎの約束

1. GitHubの [Actions — 道の駅イベント情報（全国・地域別）](https://github.com/Penta2026/michinotochu-pwa/actions/workflows/road-events.yml) から **Run workflow**。
2. **緑＝ジョブ成功**であり、新規取得成功や県別網羅を意味しない。緑になったら以下を検査:
   - `data/road_events.json`: 全国登録件数と追加県。
   - `data/road_event_quality_report.json`: `notReconfirmed`、`possibleDuplicates`、`corrected`。
   - `data/prefecture_event_coverage.json`: `summary`、`priorities`、`prefectures`。次回から利用可能。
   - 地域別診断: `data/road_event_sources_report.json`、`data/hokuriku_event_audit.json`、`data/kyushu_six_prefectures_audit.json`、`data/kyushu_okinawa_event_audit.json`。
3. 修正後はオフライン回帰テストも実行。ローカル: `PYTHONPATH=scripts python -m unittest scripts/test_regional_association_events.py scripts/test_prefecture_event_coverage.py`。
4. **各マイルストーンでこのファイルの日時・実績・未解決・次の手を更新し、チャットでも短い引継ぎを出す**。
5. 完了を宣言するのは、実際のデータと品質監査を確認したときのみ。収集器追加だけではイベント登録済みとしない。

## 主な収集器

- `scripts/collect_road_events.py`（統合入口）
- `scripts/hokkaido_events.py`、`scripts/kanto_events.py`
- `scripts/chubu_events.py`（公式PDF）
- `scripts/hokuriku_events.py`（SeleniumでJS描画後に解析、重複抑制）
- `scripts/regional_association_events.py`、`scripts/generic_region_events.py`
- `scripts/kyushu_okinawa_events.py`（くるめ・かでな）
- `scripts/kyushu_six_prefectures.py`（佐賀・長崎・熊本・大分・宮崎・鹿児島）
- `scripts/road_event_quality.py`（品質監査／既存データ保護）
- `scripts/prefecture_event_coverage.py`（新規・47県状態管理）

次回の最初の確認事項: **県別監査が47県を出力できたか・50件が維持されたか・たきかわ再確認状況**。

# 「道の途中。」道の駅イベント自動収集 — 進捗・引継ぎ

更新基準: **2026-10-10**（県別監査を実行したGitHub Actions成功後のデータを確認）  
リポジトリ: `Penta2026/michinotochu-pwa` / `main`  
ワークフロー: [road-events.yml](../.github/workflows/road-events.yml)  
イベント: [data/road_events.json](../data/road_events.json)  
**県別最新レポート**: [data/prefecture_event_coverage.json](../data/prefecture_event_coverage.json)（**初回自動生成と47県分の検査を確認済み**）

## 直近の状態（2026-10-10の実測）

- **公開イベント50件／イベント登録実績26都道県／実績なし21都府県**。
- 9地域の公式トップページの接続監査あり。**トップ接続成功は、その地域内すべての県でイベント収集が成功した意味ではない**。
- 北陸はSeleniumによるJS描画取得を実装。5件収集、表示日`dc`の違いによる重複は記事`article`番号で解消。
- 九州・沖縄は8県で各1つの情報源を設定。福岡（くるめ）、沖縄（かでな）、佐賀（しろいし）、大分（耶馬トピア）で計4件のイベント登録実績。他の4県は現時点0件。
- **品質監査: 重複候補0件、開催日訂正0件、未再確認0件**。前回未再確認だった北海道「たきかわ・大収穫祭」（10/17〜18）も最新収集で再確認できた。`exactDuplicates`の50件は、前回と同じイベントを再収集したという品質監査内の記録であり、公開データ内で50件が二重掲載されている意味ではない。
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

## 47県進捗見える化（**GitHub Actions初回実行・データ生成とも成功**）

- `scripts/prefecture_event_coverage.py` : イベントJSON、地域トップ監査、品質監査、九州8県の固定情報源設定を突き合わせて**47県全部**について状態を記録する。
- `scripts/test_prefecture_event_coverage.py` : 全47県、9地域、重複なし、対象サイトとの区別、未再確認、異常な県名を検査。
- `.github/workflows/road-events.yml` : 本収集の終了後に県別監査を実行し `data/prefecture_event_coverage.json` をコミット対象に追加。**実際に47都道府県分のレコードを生成済み**。
- `prefectures[].state` : `events_observed` / `targeted_feed_no_registered_events` / `no_registered_events` / `needs_reconfirmation`。**登録がないことは開催がないことを意味しない**。
- `targetedStationFeeds` : 九州・沖縄の8県で明示的に設定された駅情報源を列挙。ここに掲載されない別地域の収集器の存在を否定する指標ではない。
- `regionalHomepageReachable` : 公式地域トップに到達したかのみ。実際のイベント収集成否と切り離す。

## 2026-10-10 実行成功時のチェックポイント

- `data/prefecture_event_coverage.json`の`summary`: **47県、登録実績あり26県、未登録21県、イベント50件、県名異常0件、未再確認0件**。
- 9報告地域の登録件数: 北海道4、東北7、関東3、北陸5、中部12、近畿3、中国8、四国4、九州・沖縄4。計50件。
- **すでに県別の個別収集先が設定されているが登録0件の4県**: 長崎（させぼっくす９９）、熊本（すいかの里植木）、宮崎（都城NiQLL）、鹿児島（たるみずはまびら）。これらは開催日・記事構造を深掘りする。
- **個別収集先の探索が優先される未登録17都府県**: 岩手、山形、福島、茨城、栃木、群馬、千葉、東京、神奈川、静岡、福井、京都、大阪、奈良、和歌山、山口、愛媛。既存の地域収集器の有無・県別の実効カバー率は別途調査。
- **注意**: `targetedStationFeedPrefectures=8`は、九州・沖縄の特定8駅を明示した監査項目。全国で収集している県が8県しかないという意味ではない。

## 関東（茨城・栃木・群馬）第1段階実装 — GitHub Actions検証待ち

- **作業済み**: `scripts/kanto_three_prefectures.py` に公式掲載先4ルートを追加。対象は茨城県（道の駅かさま公式、茨城県ノウフクマルシェ公式告知）、栃木県（道の駅ましこ公式）、群馬県（昭和村公式イベント案内）。
- **実装意図**: 茨城の県主催会場は「道の駅」と開催場所を確認できた見出し単位だけ採用。栃木ましこはイベント記事の「開催日」を優先し、別日程のキャンペーンを混同しない。群馬はイベント見出しごとに「日時」「道の駅あぐりーむ昭和」の同一ブロック照合を必須とする。
- **検証状況**: 合成HTMLによる日付・会場・過去年対策のローカル解析テスト7件は成功。GitHub側には `scripts/test_kanto_three_prefectures.py`（8件）を追加し、ワークフローへ統合済み。**ワークフロー成功と本番データ登録はまだ未確認**。
- **監査ファイル**: `data/kanto_three_prefectures_audit.json`（次回Actionsで初生成）。4収集ルートの成否・採用件数・採用イベント例を確認する。
- **47県監査の変更**: `targetedStationFeeds` に茨城（かさま／ひたちおおた）、栃木（ましこ）、群馬（あぐりーむ昭和）を追加。対象県数は従来の九州沖縄8県から**計11県の予定**。イベント登録実績県数ではない。
- **現在の確定値**: 50件・26都道県・未登録21都府県・品質未再確認0件。**関東3県分は未算入**。
- **次にやること**: Actions「Run workflow」→緑なら `data/kanto_three_prefectures_audit.json` と `road_events.json`、`road_event_quality_report.json`、`prefecture_event_coverage.json` を確認。実際の取得件数をもとにこの引継ぎを更新する。赤なら該当テスト／パーサの実行ログを確認して修正する。
- **注意**: 茨城県主催ページは同じURLが年度更新されることがある。**令和7年の告知しか出ない場合、2026年のイベントとして登録しない**。群馬の村ページも同様。

## 未解決・優先順位

1. **関東3県（茨城・栃木・群馬）の初回GitHub Actions検証**。成功したら未登録県が減るか、県別監査の対象駅が表示されるか確認。次は関東の千葉・東京・神奈川と、近畿の未登録5府県へ広げる。
2. **九州未登録4県（長崎・熊本・宮崎・鹿児島）**。公式記事取得は成功したが開催日等を確定できていない。県別診断は `data/kyushu_six_prefectures_audit.json` にあり、熊本「すいかの里植木」は実際の本文と公開日、記事候補選別の照合を優先。
3. 東北の岩手・山形・福島、中部の静岡、中国の山口、四国の愛媛を順次調査。
4. 都道府県別の**収集実績なし**を**イベントなし**と誤認しないため、駅ごとの公式収集先・取得成功・開催日確定・イベント登録の4段階を分けて管理する。
5. 毎回の実行で `road_event_quality_report.json` の `notReconfirmed` と `possibleDuplicates` を監査し、問題発生時だけ追加調査。**北海道たきかわの前回未確認は今回解消済み**。

## 実行手順・引継ぎの約束

1. GitHubの [Actions — 道の駅イベント情報（全国・地域別）](https://github.com/Penta2026/michinotochu-pwa/actions/workflows/road-events.yml) から **Run workflow**。
2. **緑＝ジョブ成功**であり、新規取得成功や県別網羅を意味しない。緑になったら以下を検査:
   - `data/road_events.json`: 全国登録件数と追加県。
   - `data/road_event_quality_report.json`: `notReconfirmed`、`possibleDuplicates`、`corrected`。
   - `data/prefecture_event_coverage.json`: `summary`、`priorities`、`prefectures`。**生成・検証済み**。
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

次回の最初の確認事項: **関東3県4ルートの取得結果、全国50件からの増減、登録実績26県からの変化、未登録21県の変化、未再確認・重複候補の有無**。新規登録を確認してから千葉・東京・神奈川へ進める。

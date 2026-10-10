# 「道の途中。」道の駅イベント自動収集 — 進捗・引継ぎ

更新基準: **2026-10-10**（千葉・東京・神奈川の初回GitHub Actions成功後に実データを確認）  
リポジトリ: `Penta2026/michinotochu-pwa` / `main`  
ワークフロー: [road-events.yml](../.github/workflows/road-events.yml)  
イベント: [data/road_events.json](../data/road_events.json)  
**県別最新レポート**: [data/prefecture_event_coverage.json](../data/prefecture_event_coverage.json)（**初回自動生成と47県分の検査を確認済み**）

## 直近の状態（2026-10-10の実測）

- **公開イベント61件／登録実績30都道県／実績なし17都府県**（千葉県2駅の4件を追加）。
- 9地域の公式トップページの接続監査あり。**トップ接続成功は、その地域内すべての県でイベント収集が成功した意味ではない**。
- 北陸はSeleniumによるJS描画取得を実装。5件収集、表示日`dc`の違いによる重複は記事`article`番号で解消。
- 九州・沖縄は8県で各1つの情報源を設定。福岡（くるめ）、沖縄（かでな）、佐賀（しろいし）、大分（耶馬トピア）で計4件のイベント登録実績。他の4県は現時点0件。
- **最新品質監査: 重複候補0件、開催日訂正0件、未再確認1件（北海道・樹海ロード日高）**。以前のたきかわの再確認は解消済み。前回の「未再確認0件」は履歴。前回未再確認だった北海道「たきかわ・大収穫祭」（10/17〜18）も最新収集で再確認できた。`exactDuplicates`の50件は、前回と同じイベントを再収集したという品質監査内の記録であり、公開データ内で50件が二重掲載されている意味ではない。
- 注意: 50件は「現在公開しているイベントレコード」数。実際の全イベント網羅件数ではない。

## 県別の空白17都府県（現行データの実測）

| 報告地域 | イベント未登録県 | 県数 |
|---|---|---:|
| 北海道 | なし | 0 |
| 東北 | 岩手・山形・福島 | 3 |
| 関東 | 東京・神奈川 | 2 |
| 北陸 | なし | 0 |
| 中部 | 静岡 | 1 |
| 近畿 | 福井・京都・大阪・奈良・和歌山 | 5 |
| 中国 | 山口 | 1 |
| 四国 | 愛媛 | 1 |
| 九州・沖縄 | 長崎・熊本・宮崎・鹿児島 | 4 |
| **合計** | **17都府県** | **17** |

※分類はこの監査用の9地域区分。県別の地理区分と公式連絡会の所管は必ずしも同一ではない。

## 47県進捗見える化（**GitHub Actions初回実行・データ生成とも成功**）

- `scripts/prefecture_event_coverage.py` : イベントJSON、地域トップ監査、品質監査、九州8県の固定情報源設定を突き合わせて**47県全部**について状態を記録する。
- `scripts/test_prefecture_event_coverage.py` : 全47県、9地域、重複なし、対象サイトとの区別、未再確認、異常な県名を検査。
- `.github/workflows/road-events.yml` : 本収集の終了後に県別監査を実行し `data/prefecture_event_coverage.json` をコミット対象に追加。**実際に47都道府県分のレコードを生成済み**。
- `prefectures[].state` : `events_observed` / `targeted_feed_no_registered_events` / `no_registered_events` / `needs_reconfirmation`。**登録がないことは開催がないことを意味しない**。
- `targetedStationFeeds` : 九州・沖縄の8県で明示的に設定された駅情報源を列挙。ここに掲載されない別地域の収集器の存在を否定する指標ではない。
- `regionalHomepageReachable` : 公式地域トップに到達したかのみ。実際のイベント収集成否と切り離す。

## 2026-10-10 関東追加前のチェックポイント（履歴）

- `data/prefecture_event_coverage.json`の`summary`: **47県、登録実績あり26県、未登録21県、イベント50件、県名異常0件、未再確認0件**。
- 9報告地域の登録件数: 北海道4、東北7、関東3、北陸5、中部12、近畿3、中国8、四国4、九州・沖縄4。計50件。
- **すでに県別の個別収集先が設定されているが登録0件の4県**: 長崎（させぼっくす９９）、熊本（すいかの里植木）、宮崎（都城NiQLL）、鹿児島（たるみずはまびら）。これらは開催日・記事構造を深掘りする。
- **個別収集先の探索が優先される未登録17都府県**: 岩手、山形、福島、茨城、栃木、群馬、千葉、東京、神奈川、静岡、福井、京都、大阪、奈良、和歌山、山口、愛媛。既存の地域収集器の有無・県別の実効カバー率は別途調査。
- **注意**: ここに記録した`targetedStationFeedPrefectures=8`は関東追加前の値。関東3県の収集先設定後は**11県**。対象駅は県内全駅の網羅を意味しない。

## 2026-10-10 13:24 JST 関東3県初回本番実測

- **全国56件（+6）、登録実績28/47都道県（+2）、未登録19都府県（-2）**。関東は旧3件→9件。新規の茨城4件はすべて道の駅かさま、群馬2件はあぐりーむ昭和。
- **茨城**: 公式道の駅かさまから4件登録。「道の駅deあそぼ！」10/10-12、「モンブランフェア」10/17-18、「ハロウィンマーケット」10/24-25、「リフティングパフォーマンス」10/24-25。
- **群馬**: 昭和村公式より「りんご足湯」10/10-12、「しょうわむらマルシェ」10/17-18を登録。
- **栃木**: 公式ましこ10周年祭は10/11開催。収集器が取得した2レコードは**titleが空欄**だったため`road_event_quality_report.json`の`expiredOrInvalid`で新規無効として除外。今後は日付だけでなく**イベント名の非空**と同日同名記事の統合を確認する。
- **茨城県行政ソース**: `https://www.pref.ibaraki.jp/hokenfukushi/shofuku/kikaku/noufuku/documents/r7_nouhukumarusye2.html` はGitHub収集時HTTP 404。検索で令和8年度の告知は見えるが、実際の収集経路でアクセス成功と確認できるまで登録しない。
- **品質**: `notReconfirmed=[]`、`possibleDuplicates=[]`、`corrected=[]`。無効な新規イベントは栃木ましこのタイトル空欄2件。
- **修正コード**: `scripts/kanto_three_prefectures.py` の `mashiko_event_title` で空見出しを補完し、記事・開催日・タイトル単位で重複を統合。専用回帰テストを2件追加。**変更後のActionsは未実行**。

## 2026-10-10 関東ましこ修正後のGitHub Actions確認

- **全国57件（前回56件から+1）／47都道府県中29県に登録実績（+1）／登録実績なし18県（-1）**。
- 栃木県「道の駅ましこ10周年祭」**2026-10-11**、公式記事 `https://m-mashiko.com/event/4457/` が `data/road_events.json` にタイトル非空で**1件登録**。
- `data/kanto_three_prefectures_audit.json`: 公式4ルート、採用7件（茨城県行政0、かさま4、ましこ1、昭和村2）。前回のタイトル空欄2件は修正により品質監査への流入なし。
- `data/road_event_quality_report.json`: `inputPrevious=56`、`inputCollected=57`、`finalCount=57`、`notReconfirmed=[]`、`possibleDuplicates=[]`、`corrected=[]`、`expiredOrInvalid=[]`。
- `data/prefecture_event_coverage.json`: `observedPrefectures=29`、`zeroRegisteredPrefectures=18`、`targetedStationFeedPrefectures=11`、`unknownPrefectures=[]`。
- **関東の未登録**: 千葉・東京・神奈川の3都県。茨城県行政サイト `r7_nouhukumarusye2.html` は今回も **HTTP 404**。県内の「かさま」は別ルートで正常に4件登録中。
- **次の開発**: 千葉・東京・神奈川の駅別公式情報源発掘、日付・会場検証、回帰テスト追加。作業完了時には本ファイルとチャットで引継ぎを更新。

## 関東（茨城・栃木・群馬）第1段階実装 — 3県とも登録実績を確認済み

- **作業済み**: `scripts/kanto_three_prefectures.py` に公式掲載先4ルートを追加。対象は茨城県（道の駅かさま公式、茨城県ノウフクマルシェ公式告知）、栃木県（道の駅ましこ公式）、群馬県（昭和村公式イベント案内）。
- **実装意図**: 茨城の県主催会場は「道の駅」と開催場所を確認できた見出し単位だけ採用。栃木ましこはイベント記事の「開催日」を優先し、別日程のキャンペーンを混同しない。群馬はイベント見出しごとに「日時」「道の駅あぐりーむ昭和」の同一ブロック照合を必須とする。
- **検証状況**: GitHub Actions初回実行は緑。茨城4件・群馬2件を正式登録。栃木は10周年祭の開催日を検出したがタイトル空欄2件が品質監査で除外された。原因を修正し、`scripts/test_kanto_three_prefectures.py`へ空見出し・重複記事の回帰テスト2件を追加。**2026-10-10の次回GitHub Actionsで修正成功・1件登録を確認済み**。
- **監査ファイル**: `data/kanto_three_prefectures_audit.json`。初回実測は茨城県公式404・道の駅かさま4件・道の駅ましこ生データ2件（タイトル空欄で登録不可）・昭和村公式2件。**修正後のましこ10周年祭は1件の正式登録に成功**。
- **47県監査の変更**: `targetedStationFeeds` に茨城（かさま／ひたちおおた）、栃木（ましこ）、群馬（あぐりーむ昭和）を追加。**計11県の設定が実測で反映**。イベント登録実績県数ではない。
- **現在の確定値**: 57件・29都道県・未登録18都府県・品質未再確認0件・重複候補0件。茨城4件、群馬2件、栃木1件を反映済み。
- **次にやること**: 関東の未登録3都県（千葉・東京・神奈川）の道の駅公式情報源を調査する。茨城県の行政告知ルートは引き続きHTTP 404のため、URLの再確認を行う。
- **注意**: 茨城県主催ページは同じURLが年度更新されることがある。**令和7年の告知しか出ない場合、2026年のイベントとして登録しない**。群馬の村ページも同様。

## 関東・残り3都県（千葉・東京・神奈川） — 初回Actions検証済み

**実行前の基準値は全国57件・登録実績29県・未登録18都府県。実行後は61件・30県・未登録17都府県に増加。**

- `scripts/kanto_remaining_prefectures.py`（追加）: 県別の4駅公式情報源を巡回、記事ごとの日付・年・イベント名を検証、 `data/kanto_remaining_prefectures_audit.json` に候補・採用・日付未確認・取得失敗を記録。
- **千葉**: 道の駅しょうなん公式 `https://www.michinoeki-shonan.jp/`。2026-10-10「手賀沼フォトDAY」 (`/news/3181/`)、「鷹匠体験」 (`/news/3174/`)を確認。**全国造園フェスティバル** (`/news/3170/`) の主会場は手賀沼自然ふれあい緑道で、道の駅はクイズラリー拠点のみなので**道の駅開催イベントとして登録しない**。
- **千葉**: 保田小学校 `https://hotasho.jp/news-list/`。「保田小附属ようちえん3周年開園祭（2026.10.10〜12）」告知を確認。本文の曜日には不整合があるが、公式タイトルに明記された開催日を採る。イベント候補を継続監視する。
- **東京**: 八王子滝山公式 `https://www.michinoeki-hachioji.net/category/news`。10月のイベントスケジュールがあるが、カレンダー画像だけから**10月1〜31日を開催期間と推定しない**。開催日が本文に明記される個別記事のみ候補。
- **神奈川**: 湘南ちがさき公式 `https://m-shonanchigasaki.com/topics/`。10月イベントカレンダーと個別イベント記事を監視。開催日が画像のみの告知は未登録にする。別会場の催しを道の駅イベントにしない。
- `scripts/collect_road_events.py`: 新規収集器を全国合成に追加。既存データは品質監査`reconcile`で保護。
- `.github/workflows/road-events.yml`: `scripts/test_kanto_remaining_prefectures.py` （オフライン回帰テスト**13件**）実行、診断JSONをコミット対象に追加。
- `scripts/prefecture_event_coverage.py` と `scripts/test_prefecture_event_coverage.py`: 対象駅に千葉（しょうなん・保田小学校）、東京（八王子滝山）、神奈川（湘南ちがさき）を追加。最新監査で個別情報源の設定県数は11県→**14県（実測）**。これは47県中14県だけで収集している、という意味ではない。
- **初回実行結果**: GitHub Actionsは緑。千葉4件（しょうなん2・保田小学校2）を追加。東京は記事候補0件、神奈川は候補3件を確認したが、終了済み1件・開催日未確定2件で登録0件。画像カレンダーを安易に月全体の日付へ変換していない。**緑でも全国完全網羅ではない**。
- **以後**: 日付が画像だけの東京・神奈川は、安全なテキスト抽出経路や個別の公式告知を追加調査。次は近畿の未登録5府県と全国の弱い駅を調査。

## 2026-10-10 関東・千葉／東京／神奈川 初回Actions実行の確定結果

- **全国61件（+4件）／登録実績30/47都道県（+1県）／未登録17都府県（-1県）**。都道府県異常0件。
- **千葉県・しょうなん（2件）**: 「鷹匠体験」10/10、「手賀沼フォトDAY」10/10。いずれも公式記事に基づく。
- **千葉県・保田小学校（2件）**: 「保田小附属ようちえん3周年開園祭」10/10〜12、「鋸山ガイドツアー」10/10。いずれも公式お知らせから登録。
- **東京都・八王子滝山**: 公式一覧は接続成功したが、記事候補**0件**。サイト固有のイベント記事導線を別途調べること。
- **神奈川県・湘南ちがさき**: 3記事を取得、1件は過去日、2件は月間画像カレンダー中心で日付未確定。**新規登録0件**。カレンダーに掲載月があることを開催期間と誤認しないこと。
- **個別情報源の設定県数**: 14県（実際にイベントを登録できた都道県は30）。全国のほかの収集器の県別対応状況とは別指標。
- **品質監査**: `inputPrevious=57`、`inputCollected=60`、`finalCount=61`、`notReconfirmed=1`、`possibleDuplicates=0`、`expiredOrInvalid=0`、`corrected=0`。公開データは「照合済みの新着＋過去に確認した未来イベント」を保持する仕組みで、収集数と公開件数は一致しないことがある。
- **未再確認の1件**: 北海道・道の駅「樹海ロード日高」の「日高町道の駅フェスト開催のお知らせ NEW」（2026-10-11）。公式URL: `https://hokkaido-michinoeki.jp/michiekiinfo/hidakajukaiinfo/69778/`。今回の収集に無かったが公開レコードは保持。**中止・削除されたとは断定しない**。
- **次の工程**: ①北海道の未再確認を調査 ②東京・神奈川で日付が文章として明記されたイベント記事を追加探索 ③未登録の近畿5府県を深掘り。完了を宣言するのは次回の実データと品質監査を照合した後。

## 未解決・優先順位

1. **関東の残り2都県（東京・神奈川）の個別イベント記事と開催日取得**を深掘り。千葉は4件の登録実績を得た。茨城県行政サイト404も継続調査。続いて近畿の未登録5府県。
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
- `scripts/kanto_remaining_prefectures.py`（千葉・東京・神奈川4公式ソース）
- `scripts/road_event_quality.py`（品質監査／既存データ保護）
- `scripts/prefecture_event_coverage.py`（新規・47県状態管理）

次回の最初の確認事項: **全国61件・登録実績30県の維持、北海道「樹海ロード日高」の未再確認解消、東京・神奈川の個別記事の日付取得、茨城県行政ページ404、重複候補の有無**。

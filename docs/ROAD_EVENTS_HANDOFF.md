# 「道の途中。」道の駅イベント自動収集 — 進捗・引継ぎ

更新基準: **2026-10-10**（Phase 2の設定型新規イベント収集をGitHubへ実装。**Phase 2は次回Actions検証待ち**。確定値68件・32県）  
リポジトリ: `Penta2026/michinotochu-pwa` / `main`  
ワークフロー: [road-events.yml](../.github/workflows/road-events.yml)  
イベント: [data/road_events.json](../data/road_events.json)  
**県別最新レポート**: [data/prefecture_event_coverage.json](../data/prefecture_event_coverage.json)（**初回自動生成と47県分の検査を確認済み**）

## 直近の状態（2026-10-10の実測）

- **公開イベント68件／登録実績32都道県／実績なし15都府県**（奈良県クロスウェイなかまちの2件を新規登録）。
- 9地域の公式トップページの接続監査あり。**トップ接続成功は、その地域内すべての県でイベント収集が成功した意味ではない**。
- 北陸はSeleniumによるJS描画取得を実装。5件収集、表示日`dc`の違いによる重複は記事`article`番号で解消。
- 九州・沖縄は8県で各1つの情報源を設定。福岡（くるめ）、沖縄（かでな）、佐賀（しろいし）、大分（耶馬トピア）で計4件のイベント登録実績。他の4県は現時点0件。
- **最新品質監査: 未再確認0件、重複候補0件、開催日訂正0件、無効データ0件**。前回の未再確認9件は、従来収集器による再取得で全件解消。共通エンジンの本番フェイルオーバー効果は未検証（今回の監査はchecked=0）。
- 注意: 68件は「現在公開しているイベントレコード」数。実際の全国イベント網羅件数ではない。

## 県別の空白15都府県（現行データの実測）

| 報告地域 | イベント未登録県 | 県数 |
|---|---|---:|
| 北海道 | なし | 0 |
| 東北 | 岩手・山形・福島 | 3 |
| 関東 | 東京・神奈川 | 2 |
| 北陸 | なし | 0 |
| 中部 | 静岡 | 1 |
| 近畿 | 福井・大阪・和歌山 | 3 |
| 中国 | 山口 | 1 |
| 四国 | 愛媛 | 1 |
| 九州・沖縄 | 長崎・熊本・宮崎・鹿児島 | 4 |
| **合計** | **15都府県** | **15** |

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

## 2026-10-10 前回実装履歴 — 北海道の再確認改善＋近畿5府県（本番検証済み）

- **変更前のGitHub実績**: 全国61件、登録実績30/47都道県、未登録17都府県。品質監査`notReconfirmed`は北海道1件。
- **北海道**: 北の道の駅公式記事 `https://hokkaido-michinoeki.jp/michiekiinfo/hidakajukaiinfo/69778/` に「日高町道の駅フェスト」2026-10-11開催の案内が掲載されている。削除せず保護。`scripts/hokkaido_events.py` に**記事の掲載年＋道の駅名・催し名を含む本文1段落**から短い日付を復元する処理を追加。過年度の記事を今年に読み替えないテストを含む3件の回帰テストを追加。**再確認0件に戻ったかは次回Actionsで検証**。
- **東京**: 八王子滝山公式`/category/news` では2026-10-09の10月イベント予定が画像中心で確認できるが、公開記事本文で将来の個別開催日が確定できるものは現時点で特定できない。**月全体をイベント期間にしない**。URL規則やHTML構造の調査を続ける。
- **神奈川**: 湘南ちがさきはイベントカレンダー画像が中心。日時が明記された個別イベント記事を優先して追加探索し、画像の月表記を開催日へ推測変換しない。
- **近畿5府県**: `scripts/kinki_five_prefectures.py` を新設し以下の公式情報源を巡回対象に追加:
  - **福井** 若狭美浜はまびより `https://hamabiyori.com/events/`。個別記事で開催日確認後に採用。
  - **京都** 道の駅 和 `https://wachi-nagomi.com/topics/category/event/` と京丹波 味夢の里 `https://ajim.info/`。10月の祭り・実演販売、11月のマルシェ等の告知を確認。
  - **大阪** いずみ山愛の里関連の南部リージョンセンター `https://izuminambu-rc.jp/`。公共複合施設のイベントが多いため、**会場に道の駅・南部リージョンセンターの明記がある告知だけ**採用。
  - **奈良** クロスウェイなかまち `https://michi-no-eki-crosswaynakamachi.pref.nara.jp/newslist`。10/11「猿まわし」、10/31「まほろばの宴」の公式イベント告知を確認。
  - **和歌山** ねごろ歴史の丘 `https://www.negororekishinooka.jp/`。月1回のマルシェは案内されているが、**個別開催日が公式記事に明記されない限り日付を自動生成しない**。
- **安全性**: 記事タイトル・掲載年・開催日・開催場所の照合、過去イベント・中止・募集・月間カレンダーの除外。公式5府県6ルートの取得監査 `data/kinki_five_prefectures_audit.json` を追加。公式サイト到達とイベント登録は別指標。
- **全国収集・監査**: `scripts/collect_road_events.py` に新収集器を接続。`.github/workflows/road-events.yml` に専用回帰テスト11件と監査ファイルのコミットを追加。`scripts/prefecture_event_coverage.py` に近畿5府県の個別対象駅を表示し、`scripts/test_prefecture_event_coverage.py` も更新。**個別情報源を明示した県数は前回14県→次回19県の予定。これを全国網羅率と誤認しない**。
- **次回のActions**: ①Python回帰テスト成功 ②北海道の`notReconfirmed`が0件か ③京都・奈良ほか5府県の実際の採用件数 ④総件数61・登録実績30県からの変化 ⑤`possibleDuplicates`と`expiredOrInvalid` ⑥地域監査のURLエラーを確認。結果を受けて本ファイルを更新する。

## 2026-10-10 近畿5府県の初回実行結果（最新の確定チェックポイント）

- **全国61→66件（+5）、登録実績30→31県（+京都府）、未登録17→16都府県**。`data/road_events.json` と`data/prefecture_event_coverage.json`で照合。
- 京都府の追加5件:
  - 道の駅 **和**: 「3連休 道の駅 和イベント案内」10/10〜12、「いととめのぼたもち実演販売」10/11、「黒大豆枝豆もぎとり収穫体験」10/16〜11/3
  - 道の駅 **京丹波 味夢の里**: 「黒豆の枝豆祭り」10/24、「あんマルシェ2026＆譲渡会」11/15
- `data/kinki_five_prefectures_audit.json`: 京都・和 **3件**／京丹波 味夢の里 **2件**。福井（若狭美浜はまびより）候補0、大阪（いずみ山愛の里）候補0、奈良（クロスウェイなかまち）**ConnectTimeout**、和歌山（ねごろ歴史の丘）候補0。4府県のイベントがないという意味ではない。
- 地域監査`data/road_event_sources_report.json`では**近畿の公式地域トップページ到達失敗**。京都の駅個別サイトからの取得には成功している。
- **北海道「樹海ロード日高」は今回の収集で再確認された**（2026-10-11開催）。前回の未再確認1件は解消。
- **品質レポートは未再確認9件**: 茨城・かさま4件、栃木・ましこ1件、千葉・保田小学校2件、滋賀・奥永源寺渓流の里1件、佐賀・しろいし1件。いずれも`reason=not_found_in_current_collection`。接続タイムアウトが確認されたのは特に保田小学校などだが、他の7件まで接続障害と断定しない。**今後の回次で再取得して確かめる**。
- `data/road_event_quality_report.json`は`inputPrevious=61`、`inputCollected=57`、`finalCount=66`、`possibleDuplicates=[]`、`expiredOrInvalid=[]`。途中の入力収集件数と最終件数は、再確認できなかった過去の検証済みイベントを保護するため一致しない。
- **公開日メタデータ要確認**: 京都・和の「黒大豆枝豆もぎとり」記事は`publishedAt=2026-10-16`と記録されたが、基準日は10/10。開催日が公開日として解釈されている可能性があるため、採用元ページを照合して`publishedAt`を修正または空欄とすること。イベント開催日自体とは別の問題。
- **優先次工程**: ①9件の再確認／サイトタイムアウトの改善 ②記事一覧・日付の共通収集エンジンの設計（駅ごとに新ファイルを作らない仕組み）③東京・神奈川・奈良等、未登録県の個別開催日を追加調査。修正ごとに回帰テスト、Actions結果、引継ぎを更新。

## 2026-10-10 共通エンジン Phase 1 の実装履歴（GitHub Actions初回起動成功）

**基準値は全国66件、登録実績31/47都道県、未登録16都府県、未再確認9件。今回追加した共通処理の効果は未測定。**

- **新しい設定型エンジン**: `scripts/verified_station_engine.py` と `data/verified_station_source_rules.json` を追加。駅ごとに専用Pythonを増やさず、**登録済み県名・道の駅名、HTTPS公式ホスト、公式記事URLのパターン**だけを設定して、通常収集で取りこぼした「以前検証済みの未来イベント」を再確認する仕組み。
- **設定した公式情報源5駅**: 茨城・かさま、栃木・ましこ、千葉・保田小学校、滋賀・奥永源寺渓流の里、佐賀・しろいし。前回の未再確認9件に対応した公式ホストであり、**新規イベントを自動発見する設定ではない**。
- **再確認の条件**: ①前回の`road_events.json`に有効レコードが存在 ②今回の他の収集器で未取得 ③県・駅・ホスト・URLが設定と一致 ④公式の記事に当該イベント名と**同じ開催期間**の記載が存在。全部満たす場合だけ**前回レコードそのもの**を採用する。
- **通信や解析に失敗した場合**: 未再確認のまま残して旧レコードを保持。HTTP 200だけでは再確認としない。信頼できる記事に紐付けられないURLや、過去年の別イベントを勝手に登録しない。
- **診断**: `data/verified_station_reconfirmation_audit.json` を新設し、`checked`、`reconfirmed`、`failed`、`inconclusive`、駅別の明細を記録。次回Actionsで初生成。
- **テスト**: `scripts/test_verified_station_engine.py`に11件のオフライン回帰テストを追加。開催日の不一致・タイトル不一致・非公式ドメイン・通信障害・重複防止を検証する。
- **品質改善**: `scripts/road_event_quality.py`へ未来の`publishedAt`を空欄にして`futurePublicationDatesCleared`に記録する仕組みを追加。**開催日・終了日は変更しない**。関連テスト2件を追加。前回問題だった京都・和の記事が修正対象。
- **全国への組込**: `scripts/collect_road_events.py`で既存収集の後・品質統合の前に実行。`.github/workflows/road-events.yml`に新テストと監査JSONを追加。
- **設計と運用ガイド**: `docs/STATION_COLLECTOR_ENGINE.md`。次段階は`listingUrl`とCSS/URL規則を設定するだけで**未登録の新着イベントを発見**する共通HTML・WordPress収集処理。このPhase 2は**まだ未実装**。
- **次の実測確認**: GitHub ActionsをRun workflow → テスト実行成功 → 共通監査の再確認件数 → 未再確認9件からの増減 → `futurePublicationDatesCleared` → 全国66件・31県の維持／変化 → 引継ぎ更新。**グリーンでも9件すべて直ったとはみなさない**。

## 2026-10-10 最新の成功結果 — 全国68件・32県・共通エンジン初回監査

- **公開イベント68件（+2）／登録実績32/47都道県（+奈良県）／実績なし15都府県**。前回66件・31県・16都府県から更新。`data/road_events.json`の実データと`data/prefecture_event_coverage.json`の要約で確認。
- **奈良県・クロスウェイなかまちが新たに2件登録**: 10/11「日本伝統芸能 猿まわし『お猿の森』」、10/31「あの『まほろばの宴』が再びやって来る！」。公式の`/events/20261011`、`/events/20261031`の記事に基づく。
- **前回の未再確認9件はすべて解消**。`data/road_event_quality_report.json`で`notReconfirmed=[]`、`possibleDuplicates=[]`、`expiredOrInvalid=[]`、`corrected=[]`。前回66件、今回の通常収集と統合で68件。
- **共通エンジンPhase 1の診断を正確に記録**: `data/verified_station_reconfirmation_audit.json`は`checked=0`、`reconfirmed=0`、`alreadyCollected=66`、`failed=0`、`inconclusive=0`。**既存収集器が登録済み66件をすべて再取得したため、公式記事へのフォールバック取得は一度も発動しなかった**。エンジン組込と回帰テストの成功は確認できたが、**本番フォールバックでの成功件数はまだ0**。
- **未来の公開日を安全に補正**: 京都府・和の「黒大豆枝豆もぎとり収穫体験」について、`publishedAt=2026-10-16`という処理日より未来の値を`""`に変更。`futurePublicationDatesCleared`に公式記事URLと旧値を記録。イベント期間10/16〜11/3は変更なし。
- **近畿6収集先**: 和3件、京丹波 味夢の里2件、クロスウェイなかまち2件を採用。福井・大阪・和歌山は候補0件で、**イベントが存在しないとは断定しない**。今回は奈良駅サイトのタイムアウトも解消し、記事候補8件を調査。
- **最新監査**: `targetedStationFeedPrefectures=19`、異常な県名0件、地域の近畿公式トップも今回は接続成功。
- **次の工程**: 共通エンジンPhase 2（新着記事発見の設定型アダプタ）を、既存収集器は残したまま実装。開催日・掲載日・道の駅会場の確認、偽イベント除外、重複対策をテストする。東京・神奈川、近畿の福井・大阪・和歌山、他地域未登録の15都府県を対象に収集形式を広げる。初回実装後は次のActionsと引継ぎで結果を確定。

## 2026-10-10 共通収集エンジン Phase 2 — 設定型の新規記事発見を実装（Actions検証待ち）

- **本番で最後に確認した基準値は全国68件・イベント登録実績32/47県・実績なし15都府県・未再確認0件**。このPhase 2のコードによる新規取得結果は、まだ確定していない。
- **新規ファイル**: `data/station_event_discovery_sources.json`（駅別の一覧URL、公式ホスト、記事URL正規表現、CSSタイトル・本文・投稿日セレクタ、会場要件、上限記事数）、`scripts/station_discovery_engine.py`（共通HTML記事収集・新着日付判定）、`scripts/test_station_discovery_engine.py`（合成HTMLによる**16件**の安全性テスト）。
- **第1弾の対象3駅**: 東京都「八王子滝山」（公式ホーム。従来の一覧で候補0だった記事リンクを再調査）、神奈川県「湘南ちがさき」（EVENT一覧。画像だけの月間カレンダーは除外）、奈良県「クロスウェイなかまち」（既存のイベント登録実績があり、共通収集との比較・重複防止確認に使う）。
- **安全条件**: HTTPS・公式ホスト・記事URLパターン、駅ごとに設定した会場名が**公式記事本文**に含まれること、別会場と明記された記事は除外、開催日をタイトルまたはラベル付き本文で確定、開催年は公式の年記載か公開日時が必須。画像カレンダー／募集／中止／過去イベントを無条件に採用しない。リダイレクト先は自動追跡しない。
- **重複対策**: 通常収集済み＋既存の公開イベントのURLを`known`として渡し、同じ公式URLは新規収集器で生成しない。異なるURLでもイベント内容重複がないか、従来の`road_event_quality.reconcile`で監査する。
- **全国処理への接続**: `scripts/collect_road_events.py`の従来収集器の**後・共通Phase 1再確認の前**に`collect_configured_station_events`を呼び出す。個別収集器を削除・置換しないため、本番の既存68件への影響を最小化。
- **ワークフロー対応**: `.github/workflows/road-events.yml`にテスト16件と、新監査`data/station_event_discovery_audit.json`を追加。初回Actions実行で3駅ごとの`candidates`、`checked`、`knownSkipped`、`accepted`、`reasons`、`fetchFailed`、新規イベント例が記録される。
- **設計・運用説明**: `docs/STATION_COLLECTOR_ENGINE.md`に設定追加例・条件・Phase 1との違いを記載。駅の公式サイトが通常のHTML記事型なら、**次回から専用PythonではなくJSON設定だけで拡張**できる部分が増えた。PDF・画像・JavaScriptは現時点では個別解析器が必要。
- **次回実測時の手順**: GitHub Actions`Run workflow` → 16件の回帰テストとPython構文の合否 → `data/station_event_discovery_audit.json`の3駅 → `data/road_events.json`全国68件からの増減・東京／神奈川のイベント登録 → 47県・品質監査（未再確認0件、重複候補0件が維持されるか） → 引継ぎ更新。**新規登録の成功は実測でのみ宣言**。
- **次の拡張**: 実際に登録0件の福井・大阪・和歌山などを、駅ごとの公式HTML構造と開催日が確認できた順に設定追加する。現在は3駅のパイロットのみで、47県すべてがこのPhase 2で自動発見されるという意味ではない。

## 未解決・優先順位

1. **共通エンジンPhase 2の初回GitHub Actions実行検証**。東京・神奈川・奈良の3設定源の候補数と採用件数を確認。次に福井・大阪・和歌山等、HTMLで将来の催しを掲載する未登録15都府県の駅を設定追加。Phase 1フォールバック実績も継続監査。
2. **九州未登録4県（長崎・熊本・宮崎・鹿児島）**。公式記事取得は成功したが開催日等を確定できていない。県別診断は `data/kyushu_six_prefectures_audit.json` にあり、熊本「すいかの里植木」は実際の本文と公開日、記事候補選別の照合を優先。
3. 東北の岩手・山形・福島、中部の静岡、中国の山口、四国の愛媛を順次調査。
4. 都道府県別の**収集実績なし**を**イベントなし**と誤認しないため、駅ごとの公式収集先・取得成功・開催日確定・イベント登録の4段階を分けて管理する。
5. 毎回の実行で `road_event_quality_report.json` の `notReconfirmed` と `possibleDuplicates` を監査。**現在は両方0件**。京都・和の未来公開日は空欄に補正済み。再確認エンジンの有効性は、将来実際に公式一覧で取りこぼしが起きた時の`checked`・`reconfirmed`を検証する。

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
- `scripts/kinki_five_prefectures.py`（近畿5府県6収集先）
- `scripts/verified_station_engine.py`（共通エンジンPhase 1：既存記事の公式再確認）
- `scripts/station_discovery_engine.py`（共通エンジンPhase 2：新規公式HTML記事の発見）
- `data/station_event_discovery_sources.json`（公式駅別3設定）
- `data/verified_station_source_rules.json`（共通再確認の5駅公式ホスト設定）
- `scripts/road_event_quality.py`（品質監査／既存データ保護）
- `scripts/prefecture_event_coverage.py`（新規・47県状態管理）

次回の最初の確認事項: **Phase 2の3駅設定の実行結果`data/station_event_discovery_audit.json`、新規採用イベント、全国68件・32県・15都府県からの変化、未再確認／重複候補／無効データ、東京・神奈川の初登録の有無と画像カレンダー誤認防止**。

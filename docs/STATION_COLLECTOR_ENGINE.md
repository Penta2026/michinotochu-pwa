# 道の駅・共通収集エンジン移行ガイド

更新: 2026-10-10  
対象リポジトリ: `Penta2026/michinotochu-pwa`

## なぜ共通化するか

全国公式・9地域公式・駅別の収集器を組み合わせており、実際の駅ごとのHTML形式、PDF、画像、JavaScriptがばらばら。47都道府県分の専用Pythonを増やし続けるのではなく、**公式情報源と抽出ルールを設定ファイルにまとめ、共通パーサを再利用**する。

「公式サイトにアクセスできる」「記事を見つけた」「開催日が確定した」「アプリへ登録された」は**別々の状態**。正常終了＝イベント登録成功ではない。

## Phase 1（実装・初回Actions確認済み）：既存イベントの公式記事再確認

- 設定: `data/verified_station_source_rules.json`
- 共通エンジン: `scripts/verified_station_engine.py`
- 実行入口: `scripts/collect_road_events.py`（既存の各地方収集器の**後**、品質統合の**前**）
- 監査: `data/verified_station_reconfirmation_audit.json`（次のActionsで生成）
- テスト: `scripts/test_verified_station_engine.py`（11件）

基本手順：

1. 通常の地域別・駅別収集器を実行。
2. 以前に登録済みで、**今回の収集から抜けている・開催終了前**のイベントを探す。
3. 設定にある駅名・県名・HTTPSの公式ホスト・URLパスが**完全一致**するものだけ、過去に登録した公式記事のURLを再取得。
4. 正式な記事本文に**イベント固有のタイトル**と**以前に確認した開始日・終了日**がともに現れる場合に限り、元の登録済みイベントをそのまま再確認済みとして追加。
5. タイムアウト・URL変更・文章変更・日付未確定は`fetch_failed`や`title_not_found`等として監査に記録。**不明というだけで記事削除や開催中止とは判断しない**。
6. `road_event_quality.reconcile`で旧データを保護し、無効データ・重複・未再確認を監査。

初期設定は **茨城「かさま」／栃木「ましこ」／千葉「保田小学校」／滋賀「奥永源寺渓流の里」／佐賀「しろいし」** の5駅。2026-10-10時点の未再確認9件の再点検を優先した設定。**この5駅が全国の設定対象駅の総数という意味ではない**。

設定追加例（実際の変更前に公式ページを検証する）:

```json
{
  "id": "sample_station",
  "prefecture": "（確認済みの県名）",
  "roadName": "（登録済みの正式駅名）",
  "allowedHosts": ["（実際に確認した公式ホスト名）"],
  "pathPattern": "^/verified-article/[^/]+/?$"
}
```

このエンジンは**既存レコードの再確認専用**。新しい駅の収集先を追加しても、それだけで未登録の新規イベントが見つかるわけではない。新規イベントを登録する部分は、従来の収集器が引き続き担当する。

## 日付メタデータの品質ルール（同時追加）

`scripts/road_event_quality.py` に、**処理日より未来の `publishedAt` を空欄に戻す**チェックを追加。例えば2026-10-10の収集で`publishedAt=2026-10-16`なら、イベントの開始日・終了日は触らず公開日だけ除外し、`futurePublicationDatesCleared`で記録する。

## Phase 1 の本番チェック（2026-10-10 実測）

初回GitHub Actionsは緑で、**全国68件・登録実績32県・未再確認0件**。前回の未再確認9件は通常の収集器が全部取り直したため、Phase 1監査は`checked=0`/`reconfirmed=0`/`alreadyCollected=66`。共通フォールバックの起動自体は正常だが、**本番の回復効果はまだ測定できていない**。

## Phase 2（実装済み・初回GitHub Actions検証待ち）：設定型の新着記事発見

**新設ファイル**

- `data/station_event_discovery_sources.json`: 駅ごとの宣言的設定（JSON。Pythonコード追加不要）
- `scripts/station_discovery_engine.py`: 公式一覧→記事URL→個別記事の開催日・会場判定→新規イベントレコード
- `scripts/test_station_discovery_engine.py`: 16件の合成HTML回帰テスト
- `data/station_event_discovery_audit.json`: 初回Actionsで自動生成する詳細監査
- `scripts/collect_road_events.py`: 従来の全国・地域・駅別収集の後、Phase 1再確認の前に実行

**初期パイロット（3駅）**

| 都県 | 道の駅 | 一覧URL | 位置づけ |
|---|---|---|---|
| 東京 | 八王子滝山 | `https://www.michinoeki-hachioji.net/` | これまで一覧のURL形式を拾いきれなかった記事を探索 |
| 神奈川 | 湘南ちがさき | `https://m-shonanchigasaki.com/topics/` | EVENT告知を確認。画像だけの月間カレンダーは採用しない |
| 奈良 | クロスウェイなかまち | `https://michi-no-eki-crosswaynakamachi.pref.nara.jp/newslist` | 既存収集器での実績あり。共通ロジックの比較対象 |

**設定例（説明用。実運用前に公式URLと道の駅名称を照合）**

```json
{
  "id": "example",
  "enabled": true,
  "prefecture": "（駅の都道府県）",
  "roadName": "（登録済み駅名）",
  "listingUrl": "https://official.example/events/",
  "allowedHosts": ["official.example"],
  "articlePathPattern": "^/events/[0-9]+/?$",
  "listingLinkSelector": "a[href]",
  "articleSelector": "main, article",
  "titleSelectors": ["article h1", "main h1", "h1"],
  "publicationSelector": "time[datetime]",
  "requiredVenueTokens": ["（公式記事に現れる駅名）"],
  "maxArticles": 6
}
```

`publicationSelector`で公式記事の投稿日メタデータ候補を指定し、該当しない場合は共通の`publication_date`解析へフォールバックする。処理日より未来の公開日を開催年の根拠に使わない。**設定ファイルだけで収集を増やせるのは、HTMLに日付・会場が文章で掲載され、現在の共通解析と一致する駅**。画像、PDF、JavaScript表示などは次の専門アダプタが必要。

**安全上の必須条件**

1. URLはHTTPSかつ公式ホストの一致。記事URLパスも設定の正規表現に一致。リダイレクトは辿らない。
2. 記事タイトルが具体的な催しに該当し、中止・募集・月間カレンダー等ではないこと。
3. 記事タイトル自身、または`開催日時`などラベル付き本文から開催期間が確定できること。投稿年が確定できない短い月日だけでは登録しない。
4. 公式記事の本文に、その駅の名称・会場が存在すること。別会場と明示されている記事は除外。
5. 終了済みイベントや、既に通常収集・公開済みのURLは新規として作成しない。最終品質監査でも重複を確認。
6. 各駅に`candidates`/`checked`/`knownSkipped`/`accepted`/`reasons`/`fetchFailed`を記録。イベント0件を「開催なし」とは呼ばない。

**今後**: Phase 2の初回実測をもとに、HTML型の対応駅を増やし、必要なら会場セレクタ、投稿日時セレクタ、令和表記以外のカレンダー構造対応、PDF/JS専門アダプタとの接続を進める。

## 次回GitHub Actions確認

1. 新規テスト16件を含むPythonユニットテストと収集ジョブが成功するか。
2. `data/station_event_discovery_audit.json`が生成され、東京・神奈川・奈良の3駅について候補・取得・除外理由・新規採用数が記録されているか。
3. `data/road_events.json`の全国68件・登録実績32県からの増減、`road_event_quality_report.json`の未再確認・重複候補・無効データを確認。
4. 既存URLと同じイベントが新規として二重登録されていないか、カレンダーや投稿日時の誤認がないか。
5. 監査結果から共通化可能な次の駅を選び、`docs/ROAD_EVENTS_HANDOFF.md`を更新する。

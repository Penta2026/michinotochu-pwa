# 道の駅・共通収集エンジン移行ガイド

更新: 2026-10-10  
対象リポジトリ: `Penta2026/michinotochu-pwa`

## なぜ共通化するか

全国公式・9地域公式・駅別の収集器を組み合わせており、実際の駅ごとのHTML形式、PDF、画像、JavaScriptがばらばら。47都道府県分の専用Pythonを増やし続けるのではなく、**公式情報源と抽出ルールを設定ファイルにまとめ、共通パーサを再利用**する。

「公式サイトにアクセスできる」「記事を見つけた」「開催日が確定した」「アプリへ登録された」は**別々の状態**。正常終了＝イベント登録成功ではない。

## Phase 1（実装済み・GitHub Actions検証待ち）：既存イベントの公式記事再確認

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

## Phase 2（未実装・次の設計対象）：設定だけで新規イベント発見

駅ごとの `listingUrl`、`allowedHosts`、`articlePathPattern`、`titleSelector`、`dateSelectors`、`publicationDateSelector`、`venueRequirement` を設定し、HTML記事型／WordPress型の共通アダプタで新規記事を発見する。

- 公開日と開催日を混同しない。
- 開催年が根拠不足なら公開しない。
- 同じURLの別イベント・同じ日の別イベントは誤統合しない。
- 月別の画像カレンダーを1か月開催イベントに変換しない。
- オフサイト会場を道の駅開催イベントとして扱わない。
- PDF・JavaScript・複数行カレンダーは専用アダプタを引き続き利用してよい。
- 新しい情報源の追加後は**GitHub Actions実行→診断JSON→公開JSONと品質監査の照合**を必須とする。

## 次回GitHub Actions確認

1. `scripts/test_verified_station_engine.py` が他のテストとともに成功。
2. `data/verified_station_reconfirmation_audit.json` の `checked`／`reconfirmed`／`failed`／`inconclusive` を確認。
3. `data/road_event_quality_report.json` の `notReconfirmed` が**前回9件からどう変化したか**を確認。**0件になったとは事前に宣言しない**。
4. `futurePublicationDatesCleared` に京都「和」記事の未来公開日が記録され、イベント開催日は変更されないか確認。
5. `data/road_events.json` の既存66件の保持（開催終了分を除く）、登録実績31県、重複・誤登録の有無を確認。
6. 県別引継ぎ `docs/ROAD_EVENTS_HANDOFF.md` に成功・失敗を追記。

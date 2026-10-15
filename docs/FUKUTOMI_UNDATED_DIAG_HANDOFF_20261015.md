# 道の途中。福富の日付抽出失敗診断 引継ぎ（2026-10-15）

## 現状
- 前回の日次実行は成功したが、福富「レトロカーフェスタ2026」は未登録。
- data/station_event_discovery_audit.json の hiroshima_fukutomi は候補8件/確認8件/採用0件。
- レトロカーフェスタ記事は undated 判定。記事の開催日の根拠がコードから抽出できていない。
- 2026年11月3日の外部情報は見つかっているが、公式記事の本文・画像等をここでは直接検証できなかった。日付を勝手に埋め込まない。

## 今回GitHub変更
- scripts/station_discovery_engine.py: 福富の undated 記事に限り、本文抜粋（最大1200文字）、画像alt/src（最大8件）、PDFリンク（最大8件）を拒否理由と共に監査JSONへ記録する。
- 自動掲載可否ロジック・既存イベント登録・他地域の情報源は変更なし。
- 引継ぎドキュメントのみ追加。

## 次の実行
- GitHub Actions: https://github.com/Penta2026/michinotochu-pwa/actions/workflows/road-events.yml
- 実行後 data/station_event_discovery_audit.json 内 sources[id=hiroshima_fukutomi].rejectedExamples の dateDiagnosis を確認。
- 診断が本文に明示年月日を含むなら、日時抽出の対応パターンをテスト付きで改修。
- 日付が画像にのみ存在する場合は、公式画像資料を根拠として限定的な抽出/人手確認キューを設計する。画像URLからイベント開催日を推測しない。
- 大量サイトの画像OCRを無差別実行せず、個別確認する。既存品質チェックが緑でも網羅は保証しない。

## プロダクト方針
- 全国1,234駅の公式情報源を検証して追加し、新着記事を軽量巡回・詳細解析。
- 公式の開催日と会場に根拠があるイベントのみ掲載。
- 本文が解析不能な記事を「未掲載（要確認）」として追跡できる仕組みを拡充。

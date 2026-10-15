# 道の途中。広島県2駅バッチ追加 引継ぎ（2026-10-15）

## 目的
手作業で1駅ずつ収集スクリプトを増やすのではなく、既存 data/station_event_discovery_sources.json に設定をまとめて追加し、自動テストで検証する。

## GitHub変更
- data/station_event_discovery_sources.json に以下2駅の公式サイトを追加。
  - RS0960「たかの」 https://takanoyama.jp/news_event/
  - RS0959「みはら神明の里」 https://www.shinmeinosato.jp/index.html
- scripts/test_station_batch_onboarding.py: 追加駅の存在、公式サイトHTTPS、既存駅台帳との一致、設定の整合を点検。
- .github/workflows/road-events.yml: テストを日次ワークフローに追加。
- 福富、のん太の既存収集設定は維持。

## 注意
- 公式サイトがあることと、該当サイトからイベントが自動発見されることは別。
- 今回のサイトは実HTML構造の検証が未完了。記事リンクに対応できなければ候補0、イベント採用0となる。
- 公式開催日・会場が記事で明記された場合のみ既存品質判定を通じて掲載。
- 未確認のURLは登録しない。道の駅の外部イベントや過去の情報は採用しない。
- GitHub Actions の成功は、個別駅の記事適合を保証しない。

## 次回の手順
1. https://github.com/Penta2026/michinotochu-pwa/actions/workflows/road-events.yml にアクセスし Run workflow。
2. 緑の成功を確認したら、data/station_event_discovery_audit.json の hiroshima_takano と hiroshima_shinmei の candidates / checked / accepted / reasons / listingError を点検。
3. 個別記事のURLパターンや本文セレクタの不一致があれば監査結果と公式HTMLを基に修正。
4. 同じルールセット形式で広島の残駅、さらに全国をまとめて段階追加する。

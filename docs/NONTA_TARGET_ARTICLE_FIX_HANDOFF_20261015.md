# 道の途中。のん太 お米フェス未掲載修正 引継ぎ（2026-10-15）

## 事実確認
- 前回の Actions は成功。しかし data/road_events.json は60件のまま、のん太は未掲載。
- station_event_discovery_audit: hiroshima_nonta 候補13、確認10、未確認3、新規採用0。
- 目的の記事「ぶちうまい！東広島お米フェス2026を開催いたします。」は公式のイベント一覧 https://www.nonta-sakagura.com/news_category/cate01 に掲載されている。
- 同記事は2026年9月19日告知、開催日11月28日（土）〜29日（日）、会場は道の駅西条のん太の酒蔵。
- 原因：_links の preferredTitles 並べ替えは、その後 _plan_article_inspection で開催日候補のみに再ソートされ、優先名が失われていた。最大10件の検査枠から外れ得る。

## GitHub変更
- scripts/station_discovery_engine.py: _plan_article_inspection で sources の preferredTitles を最優先するように変更。既存の安全な開催日+会場検証は維持。
- scripts/test_nonta_two_day_events.py: 候補13件・枠10件の状態で、お米フェスを選択できる回帰テストを追加。
- のん太の既存2日間イベント解析ルールは変更しない。現時点では実行後の掲載可否は未確認。

## 実行・確認
https://github.com/Penta2026/michinotochu-pwa/actions/workflows/road-events.yml
1. Run workflowを実行。
2. 緑チェック後に data/station_event_discovery_audit.json の id=hiroshima_nonta の accepted、rejectedExamples を確認。
3. data/road_events.json の roadName=西条のん太の酒蔵、startDate=2026-11-28、endDate=2026-11-29 を確認。
4. 採用されなければ記事取得・本文日時・会場の判定理由を監査に基づいて追加修正。根拠のないイベントを登録しない。

## 継続方針
広島21駅の公式サイト登録、全国の個別情報源拡大、軽量更新監視+新着記事解析を別々に検証する。

# 全国優先・道の駅イベント収集 改善台帳

全国公式ソースを優先し、次に来場者等の根拠がある高稼働駅、最後に全個別駅を補完する。

現行イベント登録のない県も、未監視・イベント無しとは判定しない。

| 地域 | 現行公開件数 | 現行0件の県 | 広域サイト監査 | 次の改善 |
|---|---:|---|---|---|
| 関東 | 8 | 栃木県、千葉県、長野県 | discovery / reachable | verify_event_listing_and_build_safe_adapter |
| 九州・沖縄 | 6 | 熊本県、大分県 | discovery / reachable | verify_event_listing_and_build_safe_adapter |
| 北陸 | 4 | 富山県 | discovery / reachable | verify_event_listing_and_build_safe_adapter |
| 中部 | 13 | なし | discovery / reachable | verify_event_listing_and_build_safe_adapter |
| 北海道 | 2 | なし | discovery / reachable | verify_event_listing_and_build_safe_adapter |
| 近畿 | 9 | 福井県、滋賀県 | adapter / reachable | audit_station_matching_and_missing_prefectures |
| 中国 | 6 | 鳥取県 | adapter / reachable | audit_station_matching_and_missing_prefectures |
| 四国 | 4 | 徳島県 | adapter / reachable | audit_station_matching_and_missing_prefectures |
| 東北 | 8 | 山形県 | adapter / reachable | audit_station_matching_and_missing_prefectures |

## 広域サイト監査結果

| 地域 | サイト候補 | 追加一覧状態 | 追加候補 | エラー |
|---|---:|---|---:|---|
| 関東 | 5 | inspected | 8 | なし |
| 九州・沖縄 | 0 | inspected | 0 | なし |
| 北陸 | 0 | inspected | 0 | なし |
| 中部 | 0 | not_configured | 0 | なし |
| 北海道 | 13 | not_configured | 0 | なし |
| 近畿 | 11 | not_configured | 0 | なし |
| 中国 | 35 | not_configured | 0 | なし |
| 四国 | 5 | not_configured | 0 | なし |
| 東北 | 11 | not_configured | 0 | なし |

## 広域アダプター実績（監査データのある地域のみ）

| 地域 | 候補・検出件数 | 記事確認 | 収集器採用 | 取得障害元・頁 |
|---|---:|---:|---:|---:|
| 関東 | 4 | 4 | 1 | 不明 |
| 九州・沖縄 | 28 | 28 | 2 | 0 |
| 北陸 | 15 | 不明 | 4 | 0 |
| 中部 | None | None | None | None |
| 北海道 | 7 | 7 | 1 | 0 |
| 近畿 | 18 | 18 | 4 | 0 |
| 中国 | 695 | None | 4 | 不明 |
| 四国 | 19 | None | 3 | 不明 |
| 東北 | 6 | 6 | 5 | 0 |

※47県均等化の比較には各地域の collectionHealth を用いる。未計測の指標は null（不明）。
※北陸の検出件数は走査ページ間で重複する場合がある。収集器採用は最終公開件数ではない。
※広域サイトの候補数は検証済みイベント数ではない。

## 47都道府県の収集根拠

| 都道府県 | 公開件数 | 設定数 | 個別監査元 | 記事候補 | 記事採用 | 取得障害元 | 根拠 |
|---|---:|---:|---:|---:|---:|---:|---|
| 茨城県 | 3 | 2 | 0 | 0 | 0 | 0 | published_events_observed |
| 栃木県 | 0 | 1 | 0 | 0 | 0 | 0 | targeted_feed_configured_no_current_publication |
| 群馬県 | 1 | 1 | 0 | 0 | 0 | 0 | published_events_observed |
| 埼玉県 | 1 | 0 | 0 | 0 | 0 | 0 | published_events_observed |
| 千葉県 | 0 | 2 | 0 | 0 | 0 | 0 | targeted_feed_configured_no_current_publication |
| 東京都 | 1 | 1 | 2 | 7 | 0 | 0 | published_events_observed |
| 神奈川県 | 1 | 1 | 2 | 10 | 0 | 0 | published_events_observed |
| 山梨県 | 1 | 0 | 0 | 0 | 0 | 0 | published_events_observed |
| 長野県 | 0 | 0 | 0 | 0 | 0 | 0 | regional_homepage_only_or_unknown |
| 福岡県 | 1 | 1 | 0 | 0 | 0 | 0 | published_events_observed |
| 佐賀県 | 1 | 1 | 0 | 0 | 0 | 0 | published_events_observed |
| 長崎県 | 1 | 2 | 1 | 1 | 0 | 0 | published_events_observed |
| 熊本県 | 0 | 2 | 1 | 1 | 0 | 0 | targeted_feed_configured_no_current_publication |
| 大分県 | 0 | 1 | 0 | 0 | 0 | 0 | targeted_feed_configured_no_current_publication |
| 宮崎県 | 1 | 1 | 1 | 13 | 0 | 0 | published_events_observed |
| 鹿児島県 | 1 | 1 | 2 | 11 | 0 | 0 | published_events_observed |
| 沖縄県 | 1 | 1 | 0 | 0 | 0 | 0 | published_events_observed |
| 新潟県 | 2 | 0 | 0 | 0 | 0 | 0 | published_events_observed |
| 富山県 | 0 | 0 | 0 | 0 | 0 | 0 | regional_homepage_only_or_unknown |
| 石川県 | 2 | 0 | 0 | 0 | 0 | 0 | published_events_observed |
| 岐阜県 | 5 | 0 | 0 | 0 | 0 | 0 | published_events_observed |
| 静岡県 | 3 | 1 | 1 | 10 | 0 | 0 | published_events_observed |
| 愛知県 | 1 | 0 | 0 | 0 | 0 | 0 | published_events_observed |
| 三重県 | 4 | 0 | 0 | 0 | 0 | 0 | published_events_observed |
| 北海道 | 2 | 1 | 1 | 1 | 0 | 0 | published_events_observed |
| 福井県 | 0 | 2 | 2 | 162 | 0 | 0 | targeted_feed_configured_no_current_publication |
| 滋賀県 | 0 | 0 | 0 | 0 | 0 | 0 | regional_homepage_only_or_unknown |
| 京都府 | 3 | 2 | 0 | 0 | 0 | 0 | published_events_observed |
| 大阪府 | 2 | 2 | 2 | 12 | 0 | 0 | published_events_observed |
| 兵庫県 | 2 | 0 | 0 | 0 | 0 | 0 | published_events_observed |
| 奈良県 | 1 | 1 | 1 | 5 | 0 | 0 | published_events_observed |
| 和歌山県 | 1 | 4 | 3 | 22 | 0 | 0 | published_events_observed |
| 鳥取県 | 0 | 0 | 0 | 0 | 0 | 0 | regional_homepage_only_or_unknown |
| 島根県 | 2 | 0 | 0 | 0 | 0 | 0 | published_events_observed |
| 岡山県 | 1 | 0 | 0 | 0 | 0 | 0 | published_events_observed |
| 広島県 | 2 | 2 | 2 | 21 | 0 | 0 | published_events_observed |
| 山口県 | 1 | 2 | 2 | 10 | 0 | 0 | published_events_observed |
| 徳島県 | 0 | 0 | 0 | 0 | 0 | 0 | regional_homepage_only_or_unknown |
| 香川県 | 2 | 0 | 0 | 0 | 0 | 0 | published_events_observed |
| 愛媛県 | 1 | 1 | 3 | 21 | 0 | 0 | published_events_observed |
| 高知県 | 1 | 0 | 0 | 0 | 0 | 0 | published_events_observed |
| 青森県 | 1 | 0 | 0 | 0 | 0 | 0 | published_events_observed |
| 岩手県 | 2 | 1 | 1 | 11 | 0 | 0 | published_events_observed |
| 宮城県 | 3 | 0 | 0 | 0 | 0 | 0 | published_events_observed |
| 秋田県 | 1 | 1 | 1 | 4 | 0 | 0 | published_events_observed |
| 山形県 | 0 | 1 | 1 | 1 | 0 | 0 | targeted_feed_configured_no_current_publication |
| 福島県 | 1 | 1 | 1 | 12 | 0 | 0 | published_events_observed |

※記事採用数は個別収集器の監査値であり、アプリの最終公開件数とは異なる。
※監査日付は最新監査日のみを表し、最終成功日時の履歴ではない。
※広域サイトに接続できたことは、イベントを抽出・公開できた証明ではない。
※人気駅の優先順位は、客観的な利用・来場者データを確認後に別途付与する。
※既存のイベント公開判定・重複除去・日付／駅構内会場の照合は変更しない。

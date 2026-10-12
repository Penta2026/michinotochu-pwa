# 全国優先・道の駅イベント収集 改善台帳

全国公式ソースを優先し、次に来場者等の根拠がある高稼働駅、最後に全個別駅を補完する。

現行イベント登録のない県も、未監視・イベント無しとは判定しない。

| 地域 | 現行公開件数 | 現行0件の県 | 広域サイト監査 | 次の改善 |
|---|---:|---|---|---|
| 関東 | 8 | 栃木県、千葉県、長野県 | discovery / reachable | verify_event_listing_and_build_safe_adapter |
| 九州・沖縄 | 6 | 熊本県、大分県 | discovery / reachable | verify_event_listing_and_build_safe_adapter |
| 北陸 | 4 | 富山県 | discovery / reachable | verify_event_listing_and_build_safe_adapter |
| 中部 | 13 | なし | discovery / reachable | verify_event_listing_and_build_safe_adapter |
| 北海道 | 3 | なし | discovery / reachable | verify_event_listing_and_build_safe_adapter |
| 近畿 | 9 | 福井県、滋賀県 | adapter / reachable | audit_station_matching_and_missing_prefectures |
| 中国 | 5 | 鳥取県 | adapter / reachable | audit_station_matching_and_missing_prefectures |
| 四国 | 4 | 徳島県 | adapter / reachable | audit_station_matching_and_missing_prefectures |
| 東北 | 8 | 山形県 | adapter / reachable | audit_station_matching_and_missing_prefectures |

※広域サイトに接続できたことは、イベントを抽出・公開できた証明ではない。
※人気駅の優先順位は、客観的な利用・来場者データを確認後に別途付与する。
※既存のイベント公開判定・重複除去・日付／駅構内会場の照合は変更しない。

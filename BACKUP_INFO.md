# 道の途中。 バックアップ情報

作成日: 2026-10-05
対象: GitHub Pages版 PWA
Repository: Penta2026/michinotochu-pwa
バックアップブランチ: backup-2026-10-05-pwa-1.0.8

## バックアップ基準点
- 本番 main の基準コミット: `2c226c8fc9049935df703808bb4280ab5eee7123`
- コミットメッセージ: `Add files via upload`
- PWA Version: 1.0.8
- 公開DB Version: 2.8.20
- スポット総数: 3,573件
- 道の駅: 1,234件
- data/version.json 更新日: 2026-10-05

このバックアップブランチは、上記 main の状態を丸ごと複製した後、
バックアップ説明資料のみ追加している。
本番 main のコード・データには、この資料追加作業では変更を加えていない。

## 復元の考え方
1. このバックアップブランチをZIPで保存する。
2. 復元時はZIPを展開し、GitHub Pages用リポジトリのルートへ配置する。
3. GitHub Pagesは `main / (root)` から公開する。
4. manifest / service worker / data / assets / icons を含め、ディレクトリ構成を崩さない。
5. 公開後、PWA本体・DB・Googleマップ連携・インストール案内を確認する。

## 重要ファイル
- `index.html` : PWA本体画面
- `app.js` : アプリ主要ロジック
- `style.css` : UI
- `pwa.js` : 更新確認・DB更新
- `service-worker.js` : オフラインキャッシュ / PWA更新
- `manifest.webmanifest` : PWA定義
- `data/app_data.js` : スポットDB本体
- `data/version.json` : PWA/DB公開バージョン情報
- `data/spot_overrides.js` : スポット個別補正レイヤ
- `data/jr_stations.json` : JR駅データ
- `data/relay_stops.json` : 乗り継ぎ候補
- `install.html` : PC / Android / iPhone インストール案内
- `assets/install/PC.png`
- `assets/install/android.png`
- `assets/install/iPhone.png`

## 現時点の注意事項
- 公開DBのバージョン表示は 2.8.20。
- `spot_overrides.js` は生成済みDBを直接改変せず、実行時に補正するパッチレイヤ。
- 同ファイル内では補正レイヤの管理上、runtime metadata を 2.8.21 相当へ書き換える処理がある。
  一方、`data/version.json` の `dbVersion` は 2.8.20 のまま。
  これは大容量DBの再取得を発生させずに、スポット補正だけ反映する現在の運用による。
- バックアップから再開するときは、この差を把握した上で次回DB版番号を整理すること。

## 保存データについて
お気に入り、保存ルート、利用者設定等は利用端末側のブラウザ/PWAストレージに保存される。
このGitHubバックアップには各利用者端末の個人保存データは含まれない。

# 道の途中。PWA版 運用・更新仕様書 Ver1.0

作成日: 2026-10-05

## 現在の公開構成
- Repository: `Penta2026/michinotochu-pwa`
- GitHub Pages: https://penta2026.github.io/michinotochu-pwa/
- PWA Version: 1.0.0
- DB Version: 2.8.20
- スポット: 3,573件
- 道の駅: 1,234件

## ここまでの流れ
1. iPhoneネイティブ版ではなく、Mac不要・App Store不要のPWA方式を採用。
2. PC版のHTML/CSS/JavaScriptを母体にiPhone向けPWAを作成。
3. `manifest.webmanifest`、`service-worker.js`、`pwa.js`、PWA用アイコンを追加。
4. DBは `data/app_data.js` として同梱し、端末側へキャッシュ。
5. `data/version.json` でDB更新の有無を確認する仕組みを追加。
6. GitHub公開リポジトリを作成し、mainブランチ直下へPWA一式を配置。
7. GitHub Pagesを `main / (root)` から公開。
8. iPhone利用者はSafariから「ホーム画面に追加」で利用する。

## iPhone利用方法
1. Safariで https://penta2026.github.io/michinotochu-pwa/ を開く。
2. 共有ボタンを押す。
3. 「ホーム画面に追加」を選ぶ。
4. ホーム画面の「道の途中。」アイコンから起動する。
5. 初回はインターネット接続ありで起動することを推奨。

## DB更新の基本運用
ユーザーはPWAを入れ直さない。GitHub上のDBを更新し、iPhone側で更新する。

### DBだけ更新するとき
1. MASTER_DBを更新する。
2. PWA用 `data/app_data.js` を新DBから生成する。
3. `data/version.json` の `dbVersion` を上げる。
4. `spots`、`roadStations`、`updated` も実データに合わせる。
5. `data/app_data.js` と `data/version.json` をmainへ反映。
6. GitHub Pages反映後、PWA起動時に新版を検出。
7. ユーザーが更新を選ぶと新DBを取得・検証して差し替える。
8. 失敗した場合は旧DBを保持する。

### 現行 version.json
```json
{
  "appVersion": "1.0.0",
  "dbVersion": "2.8.20",
  "spots": 3573,
  "roadStations": 1234,
  "dataFile": "data/app_data.js",
  "updated": "2026-10-05"
}
```

## PWA本体を更新するとき
UI・機能変更時は以下も更新する。
- `index.html`
- `style.css`
- `app.js`
- `pwa.js`
- 必要に応じて `manifest.webmanifest`

さらに、
- `PWA_APP_VERSION` を上げる。
- `service-worker.js` の `SHELL_CACHE` 名も上げる。
- `data/version.json` の `appVersion` も合わせる。

例:
```js
const SHELL_CACHE='michino-shell-v1.0.1';
```

## 保存データの扱い
DB更新で消してはいけないもの:
- お気に入り
- 保存した行先
- お気に入りのルート
- 利用者設定

これらはDB本体とは別保存とし、DB差し替えでは変更しない。

## GitHub Pages設定
- Source: Deploy from a branch
- Branch: main
- Folder: / (root)
- HTTPS: 有効

mainへCommitするとGitHub Pagesが自動更新される。

## 運用ルール
- DB正本はMASTER_DB。
- PWAへ個別にデータを手入力せず、正本から `app_data.js` を生成する。
- DB変更時は必ず `dbVersion` を上げる。
- PWA機能変更時は `appVersion` とService Workerのキャッシュ版を上げる。
- 公開前に件数、主要画面、Googleマップ連携を確認する。
- 更新失敗時は旧DBを保持する。
- 利用者の保存データはDB更新で消さない。

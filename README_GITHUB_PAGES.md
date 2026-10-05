# 道の途中。 PWA Ver1.0.0

GitHub Pages公開用のPWA一式です。

## 無料公開手順
1. GitHubで公開リポジトリを1つ作成（例: `michinotochu`）
2. このZIPの中身をリポジトリ直下へアップロード
3. GitHubの `Settings` → `Pages`
4. `Build and deployment` の Source を `Deploy from a branch`
5. Branch を `main` / `(root)` にして Save
6. 数分後に `https://ユーザー名.github.io/michinotochu/` で公開
7. iPhoneのSafariで開き、共有 →「ホーム画面に追加」

## DB更新方法
通常のアプリ本体を再配布せず、次の2ファイルだけ更新できます。
- `data/app_data.js`
- `data/version.json`

`version.json` の `dbVersion` を上げて公開すると、iPhone側が起動時に更新を検出します。
更新成功までは旧DBを保持するため、通信途中で失敗しても旧データは残ります。

## 現在の収録データ
- DB Ver2.8.20
- スポット 3,573件
- 道の駅 1,234件

## 注意
お気に入り・保存した行先・設定はブラウザ端末内に保存されます。SafariのWebサイトデータを削除すると消える可能性があります。

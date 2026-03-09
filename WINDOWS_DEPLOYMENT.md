# Windows用Renderデプロイガイド

## npmがない場合の対応方法

### 方法1: Node.jsをインストール（推奨）

#### Windows
1. [Node.js公式サイト](https://nodejs.org/en/download/) からインストーラーをダウンロード
2. LTSバージョンをインストール
3. コマンドプロンプトを再起動
4. 確認: `npm --version`

#### PowerShellを使用する場合
```powershell
# Chocolateyがあれば
choco install nodejs

# またはScoop
scoop install nodejs
```

### 方法2: Renderダッシュボード直接使用（最も簡単）

#### ステップ1: Webサービス作成
1. [Renderダッシュボード](https://dashboard.render.com/) にアクセス
2. 「New +」→「Web Service」を選択
3. GitHubリポジトリを接続
4. 設定を入力：

**基本設定**
- Name: `ranshi-kun-web`
- Environment: `Python 3`
- Region: 最寄りの地域
- Branch: `main`

**ビルド設定**
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 run:app`

#### ステップ2: 環境変数設定
Environmentタブで以下を追加：
```
FLASK_ENV=production
SECRET_KEY=sfnosavnoiasherioanfeosivphizsud
ADMIN_API_TOKEN=Serika
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
LOG_LEVEL=INFO
FORCE_HTTPS=true
WEB_CONCURRENCY=4
```

#### ステップ3: データベース作成
1. 「New +」→「PostgreSQL」を選択
2. 設定：
   - Name: `ranshi-kun-db`
   - Database Name: `ranshi_kun`
   - User: `ranshi_kun_user`
   - Plan: Free

#### ステップ4: データベース接続
1. WebサービスのEnvironmentタブを開く
2. DATABASE_URL環境変数を追加
3. データベースサービスの「Connect」タブから接続文字列をコピー

#### ステップ5: デプロイ実行
1. 「Manual Deploy」をクリック
2. デプロイ完了を待機

### 方法3: WSLを使用（Windows Pro/Enterprise）

```bash
# WSLでUbuntuをインストール
wsl --install

# WSL内でNode.jsをインストール
sudo apt update
sudo apt install nodejs npm

# デプロイスクリプトを実行
chmod +x deploy-render.sh
./deploy-render.sh deploy
```

### 方法4: GitHub Actions自動デプロイ

#### .github/workflows/render.yml を作成
```yaml
name: Deploy to Render

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to Render
      run: |
        curl -X POST \
          -H "Authorization: Bearer ${{ secrets.RENDER_API_KEY }}" \
          -H "Content-Type: application/json" \
          -d '{"serviceId": "${{ secrets.RENDER_SERVICE_ID }}"}' \
          https://api.render.com/v1/services/${{ secrets.RENDER_SERVICE_ID }}/deploys
```

## トラブルシューティング

### npmコマンドが見つからない場合
```cmd
# Node.jsが正しくインストールされているか確認
where node

# PATHを確認
echo %PATH%

# Node.jsを再インストール
# 再起動
```

### PowerShellでの実行
```powershell
# スクリプト実行ポリシーを確認
Get-ExecutionPolicy

# 必要に応じてポリシーを変更
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 手動デプロイガイド実行
.\manual-deploy.sh
```

### コマンドプロンプトでの実行
```cmd
# 手動デプロイガイドを実行
manual-deploy.sh

# または直接表示
type manual-deploy.sh
```

## 推奨する方法

**最も簡単**: Renderダッシュボード直接使用
- npm不要
- GUI操作で直感的
- エラーが分かりやすい

**自動化したい場合**: Node.jsをインストールしてCLI使用
- 一度設定すれば繰り返し簡単
- CI/CD連携可能

## デプロイ後の確認

### アクセスURL
- アプリケーション: `https://your-app.onrender.com`
- 管理者ページ: `https://your-app.onrender.com/admin`
- ヘルスチェック: `https://your-app.onrender.com/health`

### 確認項目
1. ✅ ヘルスチェックが正常に応答
2. ✅ 管理者ページにログイン可能
3. ✅ データベース接続が正常
4. ✅ 予測機能が動作

## サポート

### Renderドキュメント
- [Render Docs](https://render.com/docs)
- [Troubleshooting](https://render.com/docs/troubleshooting)

### RANSHI_KUNサポート
- GitHub Issuesで問題報告
- デプロイログを共有（機密情報除く）

# Renderデプロイ時の403エラー修正ガイド

## 問題の原因
Renderで403エラーが発生する原因：
1. ボット保護が本番環境で有効になっている
2. 認証が必要なのにログインしていない
3. User-Agentがボットと判定されている

## 修正内容

### 1. ボット保護の環境対応
- `app/bot_protection.py`：開発環境では無効化、本番環境では有効化
- `FLASK_ENV=production` で本番モード動作

### 2. 認証システムの環境対応
- `app/web/views.py`：本番環境では認証必須
- `app/api/*.py`：APIエンドポイントに認証チェック追加
- 開発環境では認証スキップ可能

### 3. Render環境変数設定
以下の環境変数をRender Dashboardに設定：

```bash
# Flask Configuration
FLASK_APP=run.py
FLASK_ENV=production
SECRET_KEY=your-secret-key-here

# Database (Render PostgreSQL)
DATABASE_URL=your-postgres-url-here

# Security
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax
```

## デプロイ手順

### 1. 準備
```bash
git add .
git commit -m "Fix Render 403 authentication issues"
git push
```

### 2. Render Dashboard設定
1. Environment Variablesに上記設定を追加
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `python run.py`

### 3. 初期ユーザー作成
デプロイ後、最初にユーザー登録が必要：
1. アプリにアクセス
2. 「新規登録」タブでユーザー作成
3. 作成したユーザーでログイン

### 4. 動作確認
1. ログイン後ダッシュボードにアクセスできるか
2. UIDを登録できるか
3. 予測機能が動作するか

## トラブルシューティング

### 403エラーが続く場合
1. ログインしているか確認
2. ブラウザのUser-Agentが標準的か確認
3. Environment Variablesが正しく設定されているか確認

### 401エラーの場合
1. ログインページにリダイレクトされるはず
2. ユーザー登録してからログイン

### データベースエラーの場合
1. DATABASE_URLが正しいか確認
2. PostgreSQLが起動しているか確認

## 開発環境との違い
- 開発環境：認証不要、ボット保護無効
- 本番環境：認証必須、ボット保護有効

これにより、Renderでの403エラーが解決され、正常に動作するはずです。

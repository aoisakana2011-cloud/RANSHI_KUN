# RANSHI_KUN Renderデプロイガイド

## 概要
このガイドではRANSHI_KUN生理予測システムをRenderクラウドプラットフォームにデプロイする方法を説明します。

## Renderとは？
Renderはモダンなアプリケーションを簡単にデプロイできるクラウドプラットフォームです。
- 自動HTTPS
- 組み込みデータベース（PostgreSQL）
- 継続的デプロイ
- 簡単なスケーリング

## 前提条件

### 必要なツール
- Gitリポジトリ（GitHub、GitLabなど）
- Renderアカウント（無料）
- Node.js（Render CLI用）

### アカウント準備
1. [Render](https://render.com) でアカウントを作成
2. GitHub/GitLabアカウントを連携
3. 支払い情報を追加（無料プランでも必要）

## デプロイ方法

### 方法1: Renderダッシュボード使用（推奨）

#### ステップ1: 新規Webサービス作成
1. Renderダッシュボードで「New +」→「Web Service」を選択
2. GitHubリポジトリを接続
3. 以下の設定を入力：

**基本設定**
- **Name**: `ranshi-kun-web`
- **Environment**: `Python 3`
- **Region**: 最寄りの地域を選択
- **Branch**: `main`

**ビルド設定**
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 run:app`

**環境変数**
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

#### ステップ2: データベース作成
1. 「New +」→「PostgreSQL」を選択
2. 以下の設定：
- **Name**: `ranshi-kun-db`
- **Database Name**: `ranshi_kun`
- **User**: `ranshi_kun_user`
- **Plan**: Free

#### ステップ3: 環境変数接続
1. Webサービスに戻り、「Environment」タブを選択
2. 「Add Environment Variable」をクリック
3. データベース接続文字列を追加：
```
DATABASE_URL=postgres://ranshi_kun_user:password@hostname:5432/ranshi_kun
```
（値はデータベースサービスの「Connect」タブから取得）

#### ステップ4: デプロイ実行
1. 「Manual Deploy」をクリック
2. デプロイ完了を待機（数分）

### 方法2: Render CLI使用

#### CLIインストール
```bash
npm install -g @render/cli
```

#### デプロイスクリプト使用
```bash
# スクリプトを実行可能に
chmod +x deploy-render.sh

# デプロイ実行
./deploy-render.sh deploy
```

#### その他のコマンド
```bash
# 既存サービス更新
./deploy-render.sh update

# ログ表示
./deploy-render.sh logs

# サービスステータス確認
./deploy-render.sh status

# サービス削除
./deploy-render.sh clean
```

### 方法3: render.yaml使用

#### YAMLファイルデプロイ
1. `render.yaml` をリポジトリのルートに配置
2. Renderダッシュボードで「New +」→「Blueprint」を選択
3. リポジトリと`render.yaml`ファイルを選択
4. 「Apply Blueprint」をクリック

## 設定ファイル詳細

### render.yaml
```yaml
services:
  # Web Service
  web:
    type: web
    name: ranshi-kun-web
    env: python
    plan: free
    buildCommand: "pip install -r requirements.txt"
    startCommand: "gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 run:app"
    envVars:
      - key: FLASK_ENV
        value: production
      - key: SECRET_KEY
        value: sfnosavnoiasherioanfeosivphizsud
      # ... その他の環境変数

  # PostgreSQL Database
  database:
    type: pserv
    name: ranshi-kun-db
    plan: free
    databaseName: ranshi_kun
    user: ranshi_kun_user
```

### Dockerfile.render
Render用の最適化されたDockerfile：
- Python 3.11-slimベース
- 必要な依存関係のみ
- ヘルスチェック内蔵
- 非rootユーザーで実行

## 環境変数設定

### 必須変数
| 変数名 | 値 | 説明 |
|---------|-----|------|
| `FLASK_ENV` | `production` | Flask環境 |
| `SECRET_KEY` | `sfnosavnoiasherioanfeosivphizsud` | セキュリティキー |
| `DATABASE_URL` | Render提供の接続文字列 | データベース接続 |
| `ADMIN_API_TOKEN` | `Serika` | 管理者APIトークン |

### セキュリティ変数
| 変数名 | 値 | 説明 |
|---------|-----|------|
| `SESSION_COOKIE_SECURE` | `true` | HTTPSクッキー |
| `SESSION_COOKIE_HTTPONLY` | `true` | HTTPのみクッキー |
| `SESSION_COOKIE_SAMESITE` | `Lax` | SameSiteポリシー |
| `FORCE_HTTPS` | `true` | HTTPS強制 |

## デプロイ後の確認

### ヘルスチェック
```bash
# アプリケーションヘルス
curl https://your-app.onrender.com/health

# データベース接続
curl https://your-app.onrender.com/health/db
```

### 管理者ページ
- **URL**: `https://your-app.onrender.com/admin`
- **ユーザー名**: `admin`
- **パスワード**: `Serika`

### 監視エンドポイント
- **メトリクス**: `https://your-app.onrender.com/metrics`
- **ログ**: Renderダッシュボードの「Logs」タブ

## トラブルシューティング

### 一般的な問題

#### デプロイ失敗
```bash
# ビルドログ確認
render logs --service ranshi-kun-web --build

# よくある原因：
# - requirements.txtのエラー
# - ポート設定ミス
# - 環境変数未設定
```

#### データベース接続エラー
1. データベースサービスが起動しているか確認
2. 環境変数`DATABASE_URL`が正しいか確認
3. ネットワーク接続をテスト

#### 500エラー
```bash
# アプリケーションログ確認
render logs --service ranshi-kun-web

# よくある原因：
# - データベース移行未実行
# - 環境変数ミス
# - 依存関係不足
```

### デバッグ方法

#### ログ分析
```bash
# リアルタイムログ
render logs --service ranshi-kun-web --follow

# 特定の時間範囲
render logs --service ranshi-kun-web --since 1h
```

#### ローカルテスト
```bash
# Render環境シミュレーション
export FLASK_ENV=production
export DATABASE_URL=your-local-db
gunicorn --bind 0.0.0.0:5000 run:app
```

## パフォーマンス最適化

### Render固有の最適化
- **Freeプーン制限**: 750時間/月、512MB RAM
- **スタートアップ時間**: コールドスタートを最小化
- **ヘルスチェック**: `/health`エンドポイント実装

### スケーリング
```bash
# Standardプランにアップグレード
# - 2GB RAM
# - 無制限時間
# - カスタムドメイン
```

## セキュリティ

### Render提供のセキュリティ
- 自動HTTPS
- DDoS保護
- プライベートネットワーク

### アプリケーションセキュリティ
- セキュアクッキー設定
- CSRF保護
- レート制限
- 環境変数での機密情報管理

## バックアップと復元

### 自動バックアップ
- RenderはPostgreSQLの自動バックアップを提供
- 7日間のバックアップ保持

### 手動バックアップ
```bash
# データベースエクスポート
pg_dump $DATABASE_URL > backup.sql

# データベースインポート
psql $DATABASE_URL < backup.sql
```

## カスタムドメイン

### ドメイン設定
1. Renderダッシュボードで「Custom Domains」
2. ドメイン名を追加
3. DNSレコードを設定：
```
Type: CNAME
Name: www
Value: your-app.onrender.com
```

### SSL証明書
- Renderが自動でLet's Encrypt証明書を発行
- 無料でHTTPS対応

## コスト管理

### Freeプラン制限
- **Webサービス**: 750時間/月
- **データベース**: 256MB RAM
- **帯域**: 100GB/月

### コスト最適化
- スリープモードを活用
- 不要なサービスを停止
- 効率的なクエリを使用

## 監視とアラート

### Render監視
- サービスヘルス
- パフォーマンスメトリクス
- エラーレート

### 外部監視
```bash
# Uptime監視
curl https://your-app.onrender.com/health

# カスタムメトリクス
curl https://your-app.onrender.com/metrics
```

## サポート

### Renderサポート
- ドキュメント: [Render Docs](https://render.com/docs)
- サポート: support@render.com

### RANSHI_KUNサポート
- GitHub Issues
- デプロイログ共有
- 環境変数確認（機密情報除く）

## 次のステップ

1. **テスト**: 本番データでテスト実施
2. **監視**: アラート設定
3. **バックアップ**: 定期的なバックアップ確認
4. **ドメイン**: カスタムドメイン設定（任意）
5. **スケーリング**: 必要に応じてプランアップグレード

---

🎉 **おめでとうございます！** RANSHI_KUNがRenderで稼働しています！

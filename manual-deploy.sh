#!/bin/bash

# RANSHI_KUN Render Manual Deployment Guide
echo "🚀 RANSHI_KUN Render手動デプロイガイド"
echo "=================================="
echo ""

echo "📋 前提条件確認："
echo "1. ✅ Gitリポジトリが準備済み"
echo "2. ✅ Renderアカウントを作成済み"
echo "3. ✅ GitHub/GitLabを連携済み"
echo ""

echo "🌐 手動デプロイ手順："
echo ""
echo "📝 ステップ1: RenderダッシュボードでWebサービス作成"
echo "1. https://dashboard.render.com/ にアクセス"
echo "2. 'New +' → 'Web Service' をクリック"
echo "3. GitHubリポジトリを選択"
echo "4. 以下の設定を入力："
echo ""
echo "   Name: ranshi-kun-web"
echo "   Environment: Python 3"
echo "   Region: 最寄りの地域を選択"
echo "   Branch: main"
echo ""
echo "🔧 ステップ2: ビルド設定"
echo "Build Command: pip install -r requirements.txt"
echo "Start Command: gunicorn --bind 0.0.0.0:\$PORT --workers 4 --timeout 120 run:app"
echo ""
echo "🔐 ステップ3: 環境変数設定"
echo "Environmentタブで以下を追加："
echo ""
cat << 'EOF'
FLASK_ENV=production
SECRET_KEY=sfnosavnoiasherioanfeosivphizsud
ADMIN_API_TOKEN=Serika
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
LOG_LEVEL=INFO
FORCE_HTTPS=true
WEB_CONCURRENCY=4
EOF
echo ""
echo "🗄️ ステップ4: データベース作成"
echo "1. 'New +' → 'PostgreSQL' をクリック"
echo "2. 設定："
echo "   Name: ranshi-kun-db"
echo "   Database Name: ranshi_kun"
echo "   User: ranshi_kun_user"
echo "   Plan: Free"
echo ""
echo "🔗 ステップ5: データベース接続"
echo "1. Webサービスに戻り、Environmentタブを開く"
echo "2. 'Add Environment Variable' をクリック"
echo "3. DATABASE_URLを追加："
echo "   データベースサービスの 'Connect' タブから接続文字列をコピー"
echo ""
echo "🚀 ステップ6: デプロイ実行"
echo "1. 'Manual Deploy' をクリック"
echo "2. デプロイ完了を待機（数分）"
echo ""
echo "✅ ステップ7: 動作確認"
echo "1. https://your-app.onrender.com/health にアクセス"
echo "2. https://your-app.onrender.com/admin で管理者ページ確認"
echo "   ユーザー名: admin, パスワード: Serika"
echo ""
echo "📊 監視エンドポイント："
echo "- ヘルスチェック: /health"
echo "- データベース確認: /health/db"
echo "- メトリクス: /metrics"
echo ""
echo "🔧 トラブルシューティング："
echo "- デプロイ失敗: Renderダッシュボードの 'Logs' タブを確認"
echo "- データベースエラー: DATABASE_URL環境変数を再確認"
echo "- 500エラー: アプリケーションログで詳細を確認"
echo ""
echo "📚 詳細ドキュメント:"
echo "RENDER_DEPLOYMENT.md ファイルを参照してください"
echo ""
echo "🎉 デプロイ完了後、RANSHI_KUNが利用可能になります！"

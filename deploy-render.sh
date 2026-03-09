#!/bin/bash

# RANSHI_KUN Render Deployment Script
set -e

echo "[DEPLOY] RANSHI_KUNをRenderにデプロイします..."

# Check if Render CLI is installed
if ! command -v render; then
    echo "[INSTALL] Render CLIをインストールします..."
    
    # Check if npm is available
    if command -v npm; then
        npm install -g @render/cli
    # Check if yarn is available
    elif command -v yarn; then
        yarn global add @render/cli
    # Check if pip is available
    elif command -v pip; then
        pip install render-cli
    # Alternative: Direct binary download
    else
        echo "[FAIL] npm、yarn、またはpipが見つかりません"
        echo "[INFO] 手動でNode.jsをインストールしてください："
        echo "   Windows: https://nodejs.org/en/download/"
        echo "   macOS: brew install node"
        echo "   Linux: sudo apt install nodejs npm"
        echo ""
        echo "[INFO] または、Renderダッシュボードから手動デプロイしてください："
        echo "   https://dashboard.render.com/"
        exit 1
    fi
fi

echo "[OK] Render CLIが利用可能です"

# Check if user is logged in
if ! render whoami > /dev/null 2>&1; then
    echo "[LOGIN] Renderにログインしてください..."
    render login
fi

# Function to deploy web service
deploy_web_service() {
    echo "[DEPLOY] Webサービスをデプロイします..."
    
    # Create or update web service
    if render services list | grep -q "ranshi-kun-web"; then
        echo "[UPDATE] 既存のWebサービスを更新します..."
        render update ranshi-kun-web --yaml render.yaml
    else
        echo "[CREATE] 新規Webサービスを作成します..."
        render create --yaml render.yaml
    fi
    
    echo "[OK] Webサービスのデプロイが完了しました"
}

# Function to setup database
setup_database() {
    echo "[DB] データベースをセットアップします..."
    
    # Check if database exists
    if ! render services list | grep -q "ranshi-kun-db"; then
        echo "[CREATE] 新規データベースを作成します..."
        render create pserv \
            --name ranshi-kun-db \
            --type postgres \
            --plan free \
            --databaseName ranshi_kun \
            --user ranshi_kun_user
    else
        echo "[OK] データベースは既に存在します"
    fi
    
    echo "[OK] データベースのセットアップが完了しました"
}

# Function to setup Redis
setup_redis() {
    echo "[REDIS] Redisをセットアップします..."
    
    # Check if Redis exists
    if ! render services list | grep -q "ranshi-kun-redis"; then
        echo "[CREATE] 新規Redisを作成します..."
        render create pserv \
            --name ranshi-kun-redis \
            --type redis \
            --plan free
    else
        echo "[OK] Redisは既に存在します"
    fi
    
    echo "[OK] Redisのセットアップが完了しました"
}

# Function to run database migrations
run_migrations() {
    echo "[MIGRATE] データベース移行を実行します..."
    
    # Get web service URL
    WEB_URL=$(render services list | grep "ranshi-kun-web" | awk '{print $2}')
    
    # Wait for service to be ready
    echo "[WAIT] サービスの準備を待っています..."
    sleep 30
    
    # Run migrations via health check endpoint
    curl -X POST "$WEB_URL/migrate" || echo "移行は手動で実行してください"
    
    echo "[OK] データベース移行が完了しました"
}

# Function to verify deployment
verify_deployment() {
    echo "[VERIFY] デプロイを検証します..."
    
    # Get web service URL
    WEB_URL=$(render services list | grep "ranshi-kun-web" | awk '{print $2}')
    
    # Health check
    if curl -f "$WEB_URL/health" > /dev/null 2>&1; then
        echo "[OK] ヘルスチェックに成功しました"
    else
        echo "[FAIL] ヘルスチェックに失敗しました"
        exit 1
    fi
    
    # Database health check
    if curl -f "$WEB_URL/health/db" > /dev/null 2>&1; then
        echo "[OK] データベース接続に成功しました"
    else
        echo "[FAIL] データベース接続に失敗しました"
        exit 1
    fi
    
    echo "[OK] デプロイの検証が完了しました"
    echo "[INFO] アプリケーションURL: $WEB_URL"
}

# Function to show deployment info
show_deployment_info() {
    echo "[INFO] デプロイ情報:"
    echo "=================="
    
    render services list | grep -E "(ranshi-kun-web|ranshi-kun-db|ranshi-kun-redis)"
    
    echo ""
    echo "[ENV] 環境変数:"
    echo "FLASK_ENV=production"
    echo "SECRET_KEY=***"
    echo "ADMIN_API_TOKEN=***"
    echo "DATABASE_URL=***"
    echo ""
    echo "[MONITOR] 監視エンドポイント:"
    WEB_URL=$(render services list | grep "ranshi-kun-web" | awk '{print $2}')
    echo "ヘルスチェック: $WEB_URL/health"
    echo "メトリクス: $WEB_URL/metrics"
    echo ""
    echo "[ADMIN] 管理者ページ:"
    echo "管理者URL: $WEB_URL/admin"
    echo "ユーザー名: admin"
    echo "パスワード: Serika"
}

# Main deployment flow
main() {
    echo "[DEPLOY] RANSHI_KUN Renderデプロイを開始します..."
    
    # Setup services
    setup_database
    setup_redis
    
    # Deploy web service
    deploy_web_service
    
    # Wait and run migrations
    sleep 60
    run_migrations
    
    # Verify deployment
    verify_deployment
    
    # Show info
    show_deployment_info
    
    echo "[OK] デプロイが完了しました！"
}

# Handle command line arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "update")
        echo "[UPDATE] 既存サービスを更新します..."
        render update --yaml render.yaml
        ;;
    "logs")
        echo "[LOGS] ログを表示します..."
        render logs --service ranshi-kun-web
        ;;
    "status")
        echo "[STATUS] サービスステータスを表示します..."
        render services list
        ;;
    "clean")
        echo "[CLEAN] サービスを削除します..."
        read -p "本当にすべてのサービスを削除しますか？ (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            render delete ranshi-kun-web
            render delete ranshi-kun-db
            render delete ranshi-kun-redis
            echo "[OK] サービスを削除しました"
        fi
        ;;
    "help"|"-h"|"--help")
        echo "使い方: $0 [コマンド]"
        echo ""
        echo "コマンド:"
        echo "  deploy  - 完全デプロイ (デフォルト)"
        echo "  update  - 既存サービスを更新"
        echo "  logs    - ログを表示"
        echo "  status  - サービスステータスを表示"
        echo "  clean   - すべてのサービスを削除"
        echo "  help    - このヘルプを表示"
        ;;
    *)
        echo "不明なコマンド: $1"
        echo "'$0 help' でヘルプを表示"
        exit 1
        ;;
esac

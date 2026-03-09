# Render用設定ファイル
import os
from dotenv import load_dotenv

# Render環境の.envファイルを読み込み
load_dotenv('.env.render')

class Config:
    """基本設定"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///ranshi_kun.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 管理者設定
    ADMIN_API_TOKEN = os.environ.get('ADMIN_API_TOKEN') or 'admin-token-change-this'
    
    # セキュリティ設定
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = os.environ.get('SESSION_COOKIE_HTTPONLY', 'True').lower() == 'true'
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    
    # サーバー設定
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
    
    # ログ設定
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # SSL設定（Renderが自動でHTTPSを提供）
    FORCE_HTTPS = os.environ.get('FORCE_HTTPS', 'True').lower() == 'true'
    
    # Render固有設定
    RENDER = os.environ.get('RENDER', 'False').lower() == 'true'
    WEB_CONCURRENCY = int(os.environ.get('WEB_CONCURRENCY', '4'))
    
    # バックアップ設定
    BACKUP_ENABLED = os.environ.get('BACKUP_ENABLED', 'False').lower() == 'true'
    BACKUP_SCHEDULE = os.environ.get('BACKUP_SCHEDULE', '0 2 * * *')
    BACKUP_RETENTION_DAYS = int(os.environ.get('BACKUP_RETENTION_DAYS', 30))

class DevelopmentConfig(Config):
    """開発環境設定"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or 'sqlite:///dev_ranshi_kun.db'

class TestingConfig(Config):
    """テスト環境設定"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class ProductionConfig(Config):
    """本番環境設定"""
    DEBUG = False
    
    @classmethod
    def init_app(cls, app):
        """本番環境の初期化"""
        Config.init_app(app)
        
        # ログ設定
        import logging
        from logging.handlers import RotatingFileHandler
        
        # Renderでは標準出力が推奨
        import sys
        
        if cls.LOG_LEVEL:
            logging.basicConfig(
                level=getattr(logging, cls.LOG_LEVEL),
                format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]',
                stream=sys.stdout
            )
        
        app.logger.setLevel(getattr(logging, cls.LOG_LEVEL))
        app.logger.info('RANSHI_KUN Render production startup')

# 設定辞書
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': ProductionConfig  # Renderでは本番設定をデフォルトに
}

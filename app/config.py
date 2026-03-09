import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def _env(name, default=None):
    v = os.environ.get(name)
    return v if v is not None else default

class Config:
    SECRET_KEY = _env("SECRET_KEY", "change-this")
    DEBUG = _env("FLASK_DEBUG", "0") == "1"
    TESTING = False

    DATABASE_URL = _env("DATABASE_URL")
    if DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        data_dir = BASE_DIR / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = (data_dir / "app.db").resolve()
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + db_path.as_posix()

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    REDIS_URL = _env("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = _env("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = _env("CELERY_RESULT_BACKEND", REDIS_URL)

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = int(_env("REMEMBER_COOKIE_DURATION", 60 * 60 * 24 * 30))

    LOG_LEVEL = _env("LOG_LEVEL", "INFO")
    ADMIN_API_TOKEN = _env("ADMIN_API_TOKEN", None)

class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    AUTO_CREATE_DB = True
    LOG_LEVEL = "DEBUG"

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    AUTO_CREATE_DB = True
    LOG_LEVEL = "DEBUG"

class ProductionConfig(Config):
    DEBUG = False
    AUTO_CREATE_DB = False
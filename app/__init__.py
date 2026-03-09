import os
from flask import Flask
from logging.config import dictConfig
from .extensions import db, login_manager

def create_app(config_object=None):
    if config_object is None:
        config_object = "app.config.DevelopmentConfig" if os.environ.get("FLASK_DEBUG") == "1" else "app.config.ProductionConfig"
    app = Flask(__name__, static_folder="web/static", template_folder="web/templates")
    app.config.from_object(config_object)

    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"default": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
        "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "default"}},
        "root": {"handlers": ["console"], "level": app.config.get("LOG_LEVEL", "INFO")}
    })

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "web.login"

    with app.app_context():
        from . import models  # テーブル定義を db に登録してから create_all
        db.create_all()
        _ensure_admin_user()

    try:
        from .api.auth import bp as auth_bp
        from .api.individuals import bp as ind_bp
        from .api.admin import bp as admin_bp
        from .api.admin_extended import bp as admin_ext_bp
        from .api.predict import bp as predict_bp
        app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
        app.register_blueprint(ind_bp, url_prefix="/api/v1/individuals")
        app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")
        app.register_blueprint(admin_ext_bp, url_prefix="/api/v1/admin")
        app.register_blueprint(predict_bp, url_prefix="/api/v1")
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("API blueprint registration failed: %s", e)

    try:
        from .web.views import bp as web_bp
        app.register_blueprint(web_bp)
    except Exception:
        pass

    # Security and monitoring
    from .security import init_security
    from .monitoring import init_monitoring
    from .bot_protection import bot_detection
    init_security(app)
    init_monitoring(app)
    bot_detection.init_app(app)

    return app


def _ensure_admin_user():
    from .models import User
    if User.query.filter_by(username="admin").first() is None:
        u = User(username="admin", email=None)
        u.set_password("Serika")
        db.session.add(u)
        db.session.commit()
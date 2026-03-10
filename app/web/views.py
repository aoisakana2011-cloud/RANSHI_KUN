from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required, logout_user
import os

bp = Blueprint("web", __name__)

def is_development():
    return os.environ.get('FLASK_ENV', 'production') == 'development'

@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))
    return render_template("login.html", title="ログイン")


@bp.route("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))
    return render_template("login.html", title="ログイン")


@bp.route("/dashboard")
def dashboard():
    # 開発環境では認証をスキップ
    if not is_development() and not current_user.is_authenticated:
        return redirect(url_for("web.login"))
    return render_template("dashboard.html", title="ダッシュボード")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("web.login"))


@bp.route("/admin")
@login_required
def admin_page():
    if current_user.username != "admin":
        return redirect(url_for("web.dashboard"))
    return render_template("admin.html", title="管理者ページ")


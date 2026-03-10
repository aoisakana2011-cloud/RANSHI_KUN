# app/api/auth.py
from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from ..extensions import db
from ..models import User
from ..bot_protection import require_human, limit_ip_registrations, verify_captcha

bp = Blueprint("auth", __name__)

def is_development():
    import os
    return os.environ.get('FLASK_ENV', 'production') == 'development'

@bp.route("/register", methods=["POST"])
def register():
    # 開発環境ではボット保護をスキップ
    if not is_development():
        @require_human
        @limit_ip_registrations(max_registrations=1, time_window=3600)
        @verify_captcha()
        def protected_register():
            return _do_register()
        return protected_register()
    else:
        return _do_register()

def _do_register():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    email = data.get("email")
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "username already exists"}), 400
    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({"id": user.id, "username": user.username}), 201

@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return jsonify({"error": "invalid credentials"}), 401
    login_user(user)
    return jsonify({"message": "logged in", "username": user.username})

@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "logged out"})

@bp.route("/me", methods=["GET"])
@login_required
def me():
    return jsonify({"id": current_user.id, "username": current_user.username, "email": current_user.email})
# app/api/admin.py
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Individual, HistoryEntry, User
from ..services.prediction import load_individual, save_individual
from datetime import datetime, date
import json
from werkzeug.security import check_password_hash

bp = Blueprint("admin", __name__)

def _is_admin_request():
    token = request.headers.get("X-Admin-Token")
    expected = current_app.config.get("ADMIN_API_TOKEN")
    return expected and token and token == expected

def _is_admin_user():
    return current_user.is_authenticated and current_user.username == "admin"

@bp.route("/run-batch", methods=["POST"])
def run_batch():
    if not _is_admin_request():
        return jsonify({"error": "forbidden"}), 403
    inds = Individual.query.all()
    count = len(inds)
    return jsonify({"message": "batch triggered", "individuals": count})

@bp.route("/all-data", methods=["GET"])
@login_required
def get_all_data():
    if not _is_admin_user():
        return jsonify({"error": "admin only"}), 403
    
    # ユーザーデータ取得
    users = User.query.all()
    users_data = []
    for user in users:
        user_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "individual_count": len(user.individuals.all())
        }
        users_data.append(user_data)
    
    # 個体データ取得
    individuals = Individual.query.all()
    individuals_data = []
    for ind in individuals:
        ind_data = {
            "id": ind.id,
            "uid": ind.uid,
            "user_id": ind.user_id,
            "owner_username": ind.owner.username if ind.owner else "Unknown",
            "cycle_days": ind.cycle_days,
            "input_count": ind.input_count,
            "created_at": ind.created_at.isoformat() if ind.created_at else None
        }
        individuals_data.append(ind_data)
    
    return jsonify({
        "users": users_data,
        "individuals": individuals_data
    })

@bp.route("/users", methods=["GET"])
@login_required
def get_users():
    if not _is_admin_user():
        return jsonify({"error": "admin only"}), 403
    
    users = User.query.all()
    users_data = []
    for user in users:
        user_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "individual_count": len(user.individuals.all())
        }
        users_data.append(user_data)
    
    return jsonify({"users": users_data})

@bp.route("/users/<int:user_id>", methods=["DELETE"])
@login_required
def delete_user(user_id):
    if not _is_admin_user():
        return jsonify({"error": "admin only"}), 403
    
    user = User.query.get_or_404(user_id)
    if user.username == "admin":
        return jsonify({"error": "cannot delete admin user"}), 403
    
    # ユーザーと関連データを削除
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({"message": "user deleted successfully"})

@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
def toggle_user(user_id):
    if not _is_admin_user():
        return jsonify({"error": "admin only"}), 403
    
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    if "is_active" in data:
        user.is_active = bool(data["is_active"])
        db.session.commit()
    
    return jsonify({"message": "user status updated successfully"})

@bp.route("/individuals/<int:ind_id>", methods=["DELETE"])
@login_required
def delete_individual_admin(ind_id):
    if not _is_admin_user():
        return jsonify({"error": "admin only"}), 403
    
    ind = Individual.query.get_or_404(ind_id)
    
    # 個体と関連データを削除
    db.session.delete(ind)
    db.session.commit()
    
    return jsonify({"message": "individual deleted successfully"})

@bp.route("/delete-all-data", methods=["POST"])
@login_required
def delete_all_data():
    if not _is_admin_user():
        return jsonify({"error": "admin only"}), 403
    
    data = request.get_json()
    password = data.get("password")
    
    if not password:
        return jsonify({"error": "password required"}), 400
    
    # 管理者パスワード確認
    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user or not check_password_hash(admin_user.password_hash, password):
        return jsonify({"error": "invalid password"}), 401
    
    try:
        # adminユーザー以外の全データを削除
        non_admin_users = User.query.filter(User.username != "admin").all()
        
        for user in non_admin_users:
            # ユーザーの個体と履歴を削除
            individuals = Individual.query.filter_by(user_id=user.id).all()
            for ind in individuals:
                HistoryEntry.query.filter_by(individual_id=ind.id).delete()
                db.session.delete(ind)
            
            # ユーザーを削除
            db.session.delete(user)
        
        db.session.commit()
        return jsonify({"message": "all non-admin data deleted successfully"})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"deletion failed: {str(e)}"}), 500
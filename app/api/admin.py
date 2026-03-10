# app/api/admin.py
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Individual, HistoryEntry, User
from ..services.prediction import load_individual, save_individual
from ..services.io import delete_individual
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
    
    try:
        individuals = Individual.query.all()
        data = []
        for ind in individuals:
            # 個人データをJSONから読み込み
            ind_data = load_individual(ind.uid)
            if ind_data:
                data.append({
                    "uid": ind.uid,
                    "created_at": ind.created_at.isoformat() if ind.created_at else None,
                    "last_saved": ind_data.get("last_saved"),
                    "input_count": ind_data.get("input_count", 0),
                    "cycle_days": ind_data.get("cycle_days", 28),
                    "history_count": len(ind_data.get("history", [])),
                    "last_high_prob_date": ind_data.get("last_high_prob_date"),
                    "base_start_date": ind_data.get("base_start_date")
                })
        return jsonify({"individuals": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route("/user/<uid>/data", methods=["GET"])
@login_required
def get_user_data(uid):
    if not _is_admin_user():
        return jsonify({"error": "admin only"}), 403
    
    try:
        user_data = load_individual(uid)
        if not user_data:
            return jsonify({"error": "user not found"}), 404
        
        return jsonify({
            "uid": uid,
            "data": user_data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route("/user/<uid>/data", methods=["PUT"])
@login_required
def update_user_data(uid):
    if not _is_admin_user():
        return jsonify({"error": "admin only"}), 403
    
    try:
        new_data = request.get_json()
        if not new_data:
            return jsonify({"error": "no data provided"}), 400
        
        # データを保存
        save_individual(uid, new_data)
        
        return jsonify({"message": "data updated successfully", "uid": uid})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route("/user/<uid>/history/<entry_date>", methods=["DELETE"])
@login_required
def delete_user_entry(uid, entry_date):
    if not _is_admin_user():
        return jsonify({"error": "admin only"}), 403
    
    try:
        user_data = load_individual(uid)
        if not user_data:
            return jsonify({"error": "user not found"}), 404
        
        history = user_data.get("history", [])
        # 指定日付のエントリを削除
        original_count = len(history)
        history = [h for h in history if h.get("date") != entry_date]
        
        if len(history) == original_count:
            return jsonify({"error": "entry not found"}), 404
        
        # データを更新
        user_data["history"] = history
        user_data["input_count"] = len(history)
        user_data["last_saved"] = datetime.utcnow().isoformat()
        
        save_individual(uid, user_data)
        
        return jsonify({"message": "entry deleted successfully", "uid": uid, "date": entry_date})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route("/user/<uid>", methods=["DELETE"])
@login_required
def delete_user(uid):
    if not _is_admin_user():
        return jsonify({"error": "admin only"}), 403
    
    try:
        # 個人データを削除
        delete_individual(uid)
        
        # データベースからも削除
        individual = Individual.query.filter_by(uid=uid).first()
        if individual:
            db.session.delete(individual)
            db.session.commit()
        
        return jsonify({"message": "user deleted successfully", "uid": uid})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

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
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

@bp.route("/individuals/<int:ind_id>", methods=["PUT"])
@login_required
def update_individual_admin(ind_id):
    if not _is_admin_user():
        return jsonify({"error": "admin only"}), 403
    
    ind = Individual.query.get_or_404(ind_id)
    data = request.get_json()
    
    try:
        # 個体基本情報を更新
        if "cycle_days" in data:
            ind.cycle_days = float(data["cycle_days"])
        if "toilet_avg" in data:
            ind.toilet_avg = float(data["toilet_avg"])
        if "toilet_duration_avg" in data:
            ind.toilet_duration_avg = float(data["toilet_duration_avg"])
        if "uid" in data:
            # UIDの重複チェック
            existing = Individual.query.filter(Individual.uid == data["uid"], Individual.id != ind_id).first()
            if existing:
                return jsonify({"error": "UID already exists"}), 400
            ind.uid = data["uid"]
        
        ind.last_saved = datetime.utcnow()
        db.session.commit()
        
        return jsonify({"message": "individual updated successfully"})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"update failed: {str(e)}"}), 500

@bp.route("/individuals/<int:ind_id>/history/<int:history_id>", methods=["PUT"])
@login_required
def update_history_entry_admin(ind_id, history_id):
    if not _is_admin_user():
        return jsonify({"error": "admin only"}), 403
    
    ind = Individual.query.get_or_404(ind_id)
    entry = HistoryEntry.query.filter_by(id=history_id, individual_id=ind.id).first_or_404()
    
    data = request.get_json()
    
    try:
        # 履歴エントリを更新
        if "date" in data:
            entry.date = datetime.strptime(data["date"], "%Y-%m-%d").date()
        if "gym" in data:
            entry.gym = float(data["gym"])
        if "absent" in data:
            entry.absent = float(data["absent"])
        if "pain" in data:
            entry.pain = float(data["pain"])
        if "headache" in data:
            entry.headache = float(data["headache"])
        if "tone_pressure" in data:
            entry.tone_pressure = float(data["tone_pressure"])
        if "toilet" in data:
            entry.toilet = int(data["toilet"])
        if "toilet_time_mean" in data:
            entry.toilet_time_mean = float(data["toilet_time_mean"])
        if "toilet_duration_mean" in data:
            entry.toilet_duration_mean = float(data["toilet_duration_mean"])
        if "cough" in data:
            entry.cough = int(data["cough"])
        if "toilet_times" in data:
            entry.toilet_times = data["toilet_times"]
        if "meds" in data:
            entry.meds = data["meds"]
        if "notes" in data:
            entry.notes = data["notes"]
        
        db.session.commit()
        
        return jsonify({"message": "history entry updated successfully"})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"update failed: {str(e)}"}), 500

@bp.route("/individuals/<int:ind_id>/history/<int:history_id>", methods=["DELETE"])
@login_required
def delete_history_entry_admin(ind_id, history_id):
    if not _is_admin_user():
        return jsonify({"error": "admin only"}), 403
    
    ind = Individual.query.get_or_404(ind_id)
    entry = HistoryEntry.query.filter_by(id=history_id, individual_id=ind.id).first_or_404()
    
    try:
        db.session.delete(entry)
        db.session.commit()
        return jsonify({"message": "history entry deleted successfully"})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"deletion failed: {str(e)}"}), 500

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
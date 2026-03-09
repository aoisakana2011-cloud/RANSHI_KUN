from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models import User, Individual, HistoryEntry
from datetime import datetime, date
import csv
import io
import json
import os

bp = Blueprint("admin_extended", __name__)

def admin_required(f):
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.username != "admin":
            return jsonify({"error": "admin access required"}), 403
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@bp.route("/stats", methods=["GET"])
@login_required
@admin_required
def get_stats():
    total_users = User.query.count()
    total_individuals = Individual.query.count()
    total_entries = HistoryEntry.query.count()
    
    active_users = User.query.filter_by(is_active=True).count()
    
    today = date.today()
    today_entries = HistoryEntry.query.filter_by(date=today).count()
    
    return jsonify({
        "userCount": total_users - 1,  # Exclude admin
        "individualCount": total_individuals,
        "dataCount": total_entries,
        "activeUsers": active_users - 1,  # Exclude admin
        "todayPredictions": today_entries,
        "errorCount": 0,  # TODO: Implement error tracking
        "systemLoad": "低"  # TODO: Implement actual load monitoring
    })

@bp.route("/users", methods=["GET"])
@login_required
@admin_required
def get_users():
    users = User.query.filter(User.username != "admin").all()
    result = []
    
    for user in users:
        individual_count = Individual.query.filter_by(user_id=user.id).count()
        last_entry = HistoryEntry.query.join(Individual).filter(Individual.user_id == user.id).order_by(HistoryEntry.created_at.desc()).first()
        
        result.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "individual_count": individual_count,
            "last_active": last_entry.created_at.isoformat() if last_entry else None
        })
    
    return jsonify({"users": result})

@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_user(user_id):
    data = request.get_json() or {}
    user = User.query.get(user_id)
    if not user or user.username == "admin":
        return jsonify({"error": "user not found"}), 404
    
    user.is_active = data.get("is_active", not user.is_active)
    db.session.commit()
    
    return jsonify({"message": "user updated"})

@bp.route("/users/<int:user_id>", methods=["DELETE"])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get(user_id)
    if not user or user.username == "admin":
        return jsonify({"error": "user not found"}), 404
    
    # Delete all related data
    individuals = Individual.query.filter_by(user_id=user.id).all()
    for individual in individuals:
        HistoryEntry.query.filter_by(individual_id=individual.id).delete()
        db.session.delete(individual)
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({"message": "user deleted"})

@bp.route("/delete-all-data", methods=["POST"])
@login_required
@admin_required
def delete_all_data():
    data = request.get_json() or {}
    password = data.get("password")
    reason = data.get("reason", "")
    
    # TODO: Verify admin password
    
    # Delete all non-admin data
    non_admin_users = User.query.filter(User.username != "admin").all()
    
    for user in non_admin_users:
        individuals = Individual.query.filter_by(user_id=user.id).all()
        for individual in individuals:
            HistoryEntry.query.filter_by(individual_id=individual.id).delete()
            db.session.delete(individual)
        db.session.delete(user)
    
    db.session.commit()
    
    return jsonify({"message": "all data deleted"})

@bp.route("/backup", methods=["POST"])
@login_required
@admin_required
def create_backup():
    # Collect all data
    users = User.query.filter(User.username != "admin").all()
    backup_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "users": []
    }
    
    for user in users:
        user_data = {
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "individuals": []
        }
        
        individuals = Individual.query.filter_by(user_id=user.id).all()
        for individual in individuals:
            ind_data = {
                "uid": individual.uid,
                "cycle_days": individual.cycle_days,
                "toilet_avg": individual.toilet_avg,
                "input_count": individual.input_count,
                "weights": individual.weights,
                "params": individual.params,
                "history": []
            }
            
            entries = HistoryEntry.query.filter_by(individual_id=individual.id).all()
            for entry in entries:
                ind_data["history"].append({
                    "date": entry.date.isoformat(),
                    "gym": entry.gym,
                    "absent": entry.absent,
                    "pain": entry.pain,
                    "headache": entry.headache,
                    "tone_pressure": entry.tone_pressure,
                    "toilet": entry.toilet,
                    "raw_score": entry.raw_score,
                    "final_prob": entry.final_prob,
                    "cough": entry.cough,
                    "toilet_times": entry.toilet_times,
                    "meds": entry.meds,
                    "notes": entry.notes,
                    "created_at": entry.created_at.isoformat()
                })
            
            user_data["individuals"].append(ind_data)
        
        backup_data["users"].append(user_data)
    
    # Create JSON response
    output = io.StringIO()
    json.dump(backup_data, output, indent=2, ensure_ascii=False)
    output.seek(0)
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename=backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"}
    )

@bp.route("/export", methods=["GET"])
@login_required
@admin_required
def export_data():
    # Create CSV export
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "User", "Individual UID", "Date", "Gym", "Absent", "Pain", 
        "Headache", "Tone", "Toilet", "Raw Score", "Final Prob", 
        "Cough", "Notes", "Created At"
    ])
    
    # Data
    users = User.query.filter(User.username != "admin").all()
    for user in users:
        individuals = Individual.query.filter_by(user_id=user.id).all()
        for individual in individuals:
            entries = HistoryEntry.query.filter_by(individual_id=individual.id).all()
            for entry in entries:
                writer.writerow([
                    user.username,
                    individual.uid,
                    entry.date.isoformat(),
                    entry.gym,
                    entry.absent,
                    entry.pain,
                    entry.headache,
                    entry.tone_pressure,
                    entry.toilet,
                    entry.raw_score,
                    entry.final_prob,
                    entry.cough,
                    entry.notes or "",
                    entry.created_at.isoformat()
                ])
    
    output.seek(0)
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"}
    )

@bp.route("/system-status", methods=["GET"])
@login_required
@admin_required
def get_system_status():
    # Basic system status
    return jsonify({
        "Database Status": "Connected",
        "Total Users": User.query.count() - 1,
        "Total Individuals": Individual.query.count(),
        "Total Entries": HistoryEntry.query.count(),
        "Server Time": datetime.utcnow().isoformat(),
        "Uptime": "Unknown",  # TODO: Implement uptime tracking
        "Memory Usage": "Unknown",  # TODO: Implement memory monitoring
        "Disk Space": "Unknown"  # TODO: Implement disk space monitoring
    })

@bp.route("/logs", methods=["GET"])
@login_required
@admin_required
def get_logs():
    # TODO: Implement actual logging system
    # For now, return mock logs
    mock_logs = [
        {"timestamp": datetime.utcnow().isoformat(), "level": "INFO", "message": "System started"},
        {"timestamp": datetime.utcnow().isoformat(), "level": "INFO", "message": "User logged in"},
        {"timestamp": datetime.utcnow().isoformat(), "level": "WARNING", "message": "High system load detected"},
        {"timestamp": datetime.utcnow().isoformat(), "level": "ERROR", "message": "Database connection timeout"},
    ]
    
    return jsonify({"logs": mock_logs})

@bp.route("/comments", methods=["GET"])
@login_required
@admin_required
def get_comments():
    filter_type = request.args.get("filter", "all")
    
    # TODO: Implement actual comment system
    # For now, return mock comments
    mock_comments = [
        {
            "id": 1,
            "author": "user1",
            "content": "This is a test comment",
            "timestamp": datetime.utcnow().isoformat(),
            "flagged": filter_type == "flagged"
        },
        {
            "id": 2,
            "author": "user2", 
            "content": "Another comment here",
            "timestamp": datetime.utcnow().isoformat(),
            "flagged": False
        }
    ]
    
    if filter_type == "flagged":
        mock_comments = [c for c in mock_comments if c["flagged"]]
    elif filter_type == "recent":
        mock_comments = mock_comments[:1]
    
    return jsonify({"comments": mock_comments})

@bp.route("/comments/<int:comment_id>", methods=["PUT"])
@login_required
@admin_required
def update_comment(comment_id):
    data = request.get_json() or {}
    # TODO: Implement actual comment update
    return jsonify({"message": "comment updated"})

@bp.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def get_settings():
    if request.method == "GET":
        # 現在の設定を返す
        settings = {
            "prediction_algorithm": "advanced",
            "ml_models_enabled": True,
            "auto_optimization": True,
            "provisional_periods": True,
            "feature_engineering": True,
            "meds_categories": True,
            "toilet_time_analysis": True,
            "learning_rate_adaptive": True,
            "model_training_threshold": 10,
            "backup_frequency": "daily",
            "data_retention_days": 365,
            "max_prediction_range": 60,
            "confidence_threshold": 0.6
        }
        return jsonify(settings)
    
    elif request.method == "POST":
        # 設定を更新
        data = request.get_json() or {}
        
        # 設定ファイルに保存（実際の実装ではDBや設定ファイルを使用）
        settings_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'admin_settings.json')
        try:
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return jsonify({"message": "設定を更新しました"})
        except Exception as e:
            return jsonify({"error": f"設定の更新に失敗しました: {str(e)}"}), 500

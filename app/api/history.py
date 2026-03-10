# app/api/history.py
from flask import Blueprint, request, jsonify
from flask_login import current_user
from datetime import datetime
from ..models import Individual, HistoryEntry
import os

def is_development():
    return os.environ.get('FLASK_ENV', 'production') == 'development'

bp = Blueprint("history", __name__)

@bp.route("/<uid>", methods=["GET"])
def get_history(uid):
    # 本番環境では認証を必須にする
    if not is_development() and not current_user.is_authenticated:
        return jsonify({"error": "authentication required"}), 401
        
    if is_development():
        # 開発環境では全ユーザーのデータを表示
        ind = Individual.query.filter_by(uid=uid).first()
    else:
        # 本番環境では現在のユーザーのデータのみ表示
        ind = Individual.query.filter_by(uid=uid, user_id=current_user.id).first()
        
    if not ind:
        return jsonify([])  # Return empty list instead of error for development
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    q = HistoryEntry.query.filter_by(individual_id=ind.id)
    if start_str:
        try:
            start = datetime.strptime(start_str, "%Y-%m-%d").date()
            q = q.filter(HistoryEntry.date >= start)
        except ValueError:
            return jsonify({"error": "invalid start date"}), 400
    if end_str:
        try:
            end = datetime.strptime(end_str, "%Y-%m-%d").date()
            q = q.filter(HistoryEntry.date <= end)
        except ValueError:
            return jsonify({"error": "invalid end date"}), 400
    entries = q.order_by(HistoryEntry.date.asc()).all()
    res = []
    for h in entries:
        res.append({
            "id": h.id,
            "date": h.date.isoformat(),
            "gym": h.gym,
            "absent": h.absent,
            "pain": h.pain,
            "headache": h.headache,
            "tone_pressure": h.tone_pressure,
            "toilet": h.toilet,
            "toilet_time_mean": h.toilet_time_mean,
            "toilet_duration_mean": h.toilet_duration_mean,
            "raw_score": h.raw_score,
            "final_prob": h.final_prob,
            "cough": h.cough,
            "toilet_times": h.toilet_times or [],
            "meds": h.meds or [],
            "notes": h.notes,
            "created_at": h.created_at.isoformat(),
        })
    return jsonify(res)
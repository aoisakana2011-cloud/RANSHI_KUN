# app/api/individuals.py
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Individual, HistoryEntry
from datetime import datetime, date

bp = Blueprint("individuals", __name__)

def _individual_to_dict(ind, include_history=False):
    d = {
        "id": ind.id,
        "uid": ind.uid,
        "cycle_days": ind.cycle_days,
        "toilet_avg": ind.toilet_avg,
        "toilet_duration_avg": ind.toilet_duration_avg,
        "input_count": ind.input_count,
        "last_high_prob_date": ind.last_high_prob_date.isoformat() if ind.last_high_prob_date else None,
        "base_prob": ind.base_prob,
        "base_start_date": ind.base_start_date.isoformat() if ind.base_start_date else None,
        "pending_candidate_start": ind.pending_candidate_start.isoformat() if ind.pending_candidate_start else None,
        "toilet_time_mean": ind.toilet_time_mean,
        "last_saved": ind.last_saved.isoformat() if ind.last_saved else None,
        "weights": ind.weights or {},
        "params": ind.params or {},
        "models": ind.models or {},
    }
    if include_history:
        d["history"] = [
            {
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
            }
            for h in ind.history_entries.order_by(HistoryEntry.date.asc()).all()
        ]
    return d

@bp.route("", methods=["GET"])
@login_required
def list_individuals():
    inds = Individual.query.filter_by(user_id=current_user.id).all()
    return jsonify([_individual_to_dict(i, include_history=False) for i in inds])

@bp.route("", methods=["POST"])
@login_required
def create_individual():
    data = request.get_json() or {}
    uid = data.get("uid")
    if not uid:
        return jsonify({"error": "uid required"}), 400
    if Individual.query.filter_by(uid=uid).first():
        return jsonify({"error": "uid already exists"}), 400
    ind = Individual(
        uid=uid,
        user_id=current_user.id,
        cycle_days=data.get("cycle_days", 28.0),
        toilet_avg=data.get("toilet_avg", 7.0),
        toilet_duration_avg=data.get("toilet_duration_avg", 0.0),
        input_count=0,
        last_high_prob_date=date.today(),
        base_prob=0.0,
        weights=data.get("weights") or {},
        params=data.get("params") or {},
        models=data.get("models") or {},
    )
    db.session.add(ind)
    db.session.commit()
    return jsonify(_individual_to_dict(ind)), 201

@bp.route("/<uid>", methods=["GET"])
@login_required
def get_individual(uid):
    ind = Individual.query.filter_by(uid=uid, user_id=current_user.id).first()
    if not ind:
        return jsonify({"error": "not found"}), 404
    include_history = request.args.get("include_history") == "1"
    return jsonify(_individual_to_dict(ind, include_history=include_history))

@bp.route("/<uid>", methods=["PATCH"])
@login_required
def update_individual(uid):
    ind = Individual.query.filter_by(uid=uid, user_id=current_user.id).first()
    if not ind:
        return jsonify({"error": "not found"}), 404
    data = request.get_json() or {}
    for field in ["cycle_days", "toilet_avg", "toilet_duration_avg"]:
        if field in data:
            setattr(ind, field, data[field])
    if "weights" in data:
        ind.weights = data["weights"]
    if "params" in data:
        ind.params = data["params"]
    ind.last_saved = datetime.utcnow()
    db.session.commit()
    return jsonify(_individual_to_dict(ind))

@bp.route("/<uid>", methods=["DELETE"])
@login_required
def delete_individual(uid):
    ind = Individual.query.filter_by(uid=uid, user_id=current_user.id).first()
    if not ind:
        return jsonify({"error": "not found"}), 404
    db.session.delete(ind)
    db.session.commit()
    return jsonify({"message": "deleted"})

@bp.route("/<uid>/entries", methods=["POST"])
@login_required
def add_entry(uid):
    ind = Individual.query.filter_by(uid=uid, user_id=current_user.id).first()
    if not ind:
        return jsonify({"error": "not found"}), 404
    data = request.get_json() or {}
    date_str = data.get("date")
    if not date_str:
        return jsonify({"error": "date required"}), 400
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "invalid date format"}), 400
    entry = HistoryEntry(
        individual_id=ind.id,
        date=d,
        gym=data.get("gym", 0.0),
        absent=data.get("absent", 0.0),
        pain=data.get("pain", 0.0),
        headache=data.get("headache", 0.0),
        tone_pressure=data.get("tone_pressure", 0.0),
        toilet=data.get("toilet", 0.0),
        toilet_time_mean=data.get("toilet_time_mean", 0.0),
        toilet_duration_mean=data.get("toilet_duration_mean", 0.0),
        raw_score=data.get("raw_score", 0.0),
        final_prob=data.get("final_prob", 0.0),
        cough=data.get("cough", 0.0),
        toilet_times=data.get("toilet_times") or [],
        meds=data.get("meds") or [],
        notes=data.get("notes"),
    )
    ind.input_count = (ind.input_count or 0) + 1
    ind.last_saved = datetime.utcnow()
    db.session.add(entry)
    db.session.commit()
    return jsonify({"id": entry.id}), 201
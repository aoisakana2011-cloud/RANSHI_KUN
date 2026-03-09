import os
import json
import math
import numpy as np
from datetime import datetime, timedelta, time, date
from typing import Dict, List, Any, Tuple, Optional
from .ml_advanced import *
from .ml_models import schedule_and_train_models_for_uid, fused_prediction_with_models
from .io import load_individual, save_individual
from .parsing import parse_datetime_str
from .aggregation import aggregate_history_by_date, collapse_entries_for_date

def evaluate_and_maybe_switch_base(uid, udata):
    hist = udata.get("history", [])
    agg = aggregate_history_by_date(hist)
    if not agg:
        return False
    dates = sorted(agg.keys())
    first_date = datetime.strptime(dates[0], "%Y-%m-%d").date()
    base_start = udata.get("base_start_date", None)
    base_prob = float(udata.get("base_prob", 0.0))
    pending = udata.get("pending_candidate_start", None)
    if not base_start:
        candidate = first_date
        candidate_score = score_sum_for_period(agg, end_date=candidate + timedelta(days=SCORE_PERIOD_DAYS-1), days=SCORE_PERIOD_DAYS)
        udata["base_start_date"] = candidate.strftime("%Y-%m-%d")
        udata["base_prob"] = float(candidate_score)
        udata["pending_candidate_start"] = None
        return True
    if pending:
        try:
            pending_date = datetime.strptime(pending, "%Y-%m-%d").date()
        except Exception:
            pending_date = None
        if pending_date:
            if datetime.now().date() >= pending_date + timedelta(days=SCORE_PERIOD_DAYS-1):
                candidate_score = score_sum_for_period(agg, end_date=pending_date + timedelta(days=SCORE_PERIOD_DAYS-1), days=SCORE_PERIOD_DAYS)
                if candidate_score > base_prob:
                    udata["base_start_date"] = pending_date.strftime("%Y-%m-%d")
                    udata["base_prob"] = float(candidate_score)
                udata["pending_candidate_start"] = None
                return True
    try:
        base_start_date = datetime.strptime(udata.get("base_start_date", dates[0]), "%Y-%m-%d").date()
    except Exception:
        base_start_date = first_date
    for d in dates:
        d_date = datetime.strptime(d, "%Y-%m-%d").date()
        if base_start_date < d_date <= base_start_date + timedelta(days=16):
            if datetime.now().date() >= d_date + timedelta(days=SCORE_PERIOD_DAYS-1):
                candidate_score = score_sum_for_period(agg, end_date=d_date + timedelta(days=SCORE_PERIOD_DAYS-1), days=SCORE_PERIOD_DAYS)
                if candidate_score > base_prob:
                    udata["base_start_date"] = d_date.strftime("%Y-%m-%d")
                    udata["base_prob"] = float(candidate_score)
                    udata["pending_candidate_start"] = None
                    return True
            else:
                udata["pending_candidate_start"] = d_date.strftime("%Y-%m-%d")
                return False
    return False

def update_cycle_on_observation(uid, observed_date, observed_prob, udata):
    if observed_prob < HIGH_THRESHOLD:
        return False
    try:
        last_high = datetime.strptime(udata.get("last_high_prob_date", observed_date.strftime("%Y-%m-%d")), "%Y-%m-%d")
    except Exception:
        last_high = observed_date
    cycle = float(udata.get("cycle_days", 28.0))
    predicted_center = last_high + timedelta(days=cycle)
    shift = (observed_date - predicted_center).days
    input_count = udata.get("input_count", 0)
    if input_count < MIN_STRONG_UPDATE_DAYS:
        alpha = 0.0
    else:
        alpha = 0.30
    new_cycle = (1 - alpha) * cycle + alpha * (cycle + shift)
    new_cycle = max(20.0, min(40.0, new_cycle))
    udata["cycle_days"] = float(new_cycle)
    udata["last_high_prob_date"] = observed_date.strftime("%Y-%m-%d")
    udata["last_observed_prob"] = float(observed_prob)
    return True

def _create_default_individual(uid):
    now = datetime.now()
    return {
        "uid": uid,
        "cycle_days": 28.0,
        "toilet_avg": 7.0,
        "toilet_duration_avg": 0.0,
        "input_count": 0,
        "last_high_prob_date": now.strftime("%Y-%m-%d"),
        "base_prob": 0.0,
        "base_start_date": "",
        "pending_candidate_start": None,
        "history": [],
        "toilet_time_mean": None,
        "provisional_periods": [],
        "last_saved": now.isoformat(),
        "models": {},
        "weights": {
            "gym": GYM_WEIGHT_INIT, 
            "absent": ABSENT_WEIGHT_INIT, 
            "pain": PAIN_WEIGHT_INIT, 
            "headache": HEADACHE_WEIGHT_INIT, 
            "tone": TONE_WEIGHT_INIT
        },
        "params": {
            "cough_max_multiplier": COUGH_MAX_MULTIPLIER_INIT, 
            "cough_min_multiplier": COUGH_MIN_MULTIPLIER_INIT, 
            "group1_target_prob": GROUP1_TARGET_PROB_INIT, 
            "group2_target_prob": GROUP2_TARGET_PROB_INIT, 
            "group3_multiplier": GROUP3_MULTIPLIER_INIT, 
            "group4_add": GROUP4_ADD_INIT, 
            "score_shift": SCORE_SHIFT_INIT
        }
    }

def load_meds_list():
    meds_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'meds_list.json')
    if os.path.exists(meds_file):
        try:
            with open(meds_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _compute_and_save_entry(uid: str, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    dt_str = payload.get("datetime") or payload.get("date")
    dt = parse_datetime_str(dt_str) if dt_str else None
    if dt is None:
        dt = datetime.utcnow()
    today_str = dt.date().strftime("%Y-%m-%d")
    entry_tf = time_weight_factor_from_timeobj(dt.time())

    udata = load_individual(uid) or _create_default_individual(uid)
    w = dict(udata.get("weights", {}))
    default_weights = {"gym": GYM_WEIGHT_INIT, "absent": ABSENT_WEIGHT_INIT, "pain": PAIN_WEIGHT_INIT, "headache": HEADACHE_WEIGHT_INIT, "tone": TONE_WEIGHT_INIT}
    w.update({k: v for k, v in default_weights.items() if k not in w})
    
    p = dict(udata.get("params", {}))
    default_params = {
        "cough_max_multiplier": COUGH_MAX_MULTIPLIER_INIT,
        "cough_min_multiplier": COUGH_MIN_MULTIPLIER_INIT,
        "group1_target_prob": GROUP1_TARGET_PROB_INIT,
        "group2_target_prob": GROUP2_TARGET_PROB_INIT,
        "group3_multiplier": GROUP3_MULTIPLIER_INIT,
        "group4_add": GROUP4_ADD_INIT,
        "score_shift": SCORE_SHIFT_INIT
    }
    p.update({k: v for k, v in default_params.items() if k not in p})

    gym = int(payload.get("gym", 0) or 0)
    absent = int(payload.get("absent", 0) or 0)
    pain = int(payload.get("pain", 0) or 0)
    headache = int(payload.get("headache", 0) or 0)
    tone = int(payload.get("tone_pressure", payload.get("tone", 0) or 0))
    cough = int(payload.get("cough", 0) or 0)

    raw_score = (w["gym"] * gym + w["absent"] * absent + w["pain"] * pain + w["headache"] * headache + w["tone"] * tone) * entry_tf

    cough_multiplier = p["cough_max_multiplier"] - (p["cough_max_multiplier"] - p["cough_min_multiplier"]) * (cough / 4.0)
    raw_score *= cough_multiplier

    toilet_times_payload = payload.get("toilet_times") or []
    toilet_count = len(toilet_times_payload)
    
    if toilet_count > 0:
        avg_duration = sum(t.get("duration_min", 0) for t in toilet_times_payload) / toilet_count
        avg_duration = max(0, min(avg_duration, 30))
        
        history = udata.get("history", [])
        if history:
            all_durations = []
            for entry in history[-20:]:
                for t in entry.get("toilet_times", []):
                    if t.get("duration_min"):
                        all_durations.append(t["duration_min"])
            
            if all_durations:
                historical_avg = sum(all_durations) / len(all_durations)
                target_duration = historical_avg + 5.0
            else:
                target_duration = 5.0
        else:
            target_duration = 5.0
        
        duration_score = 1.0 - abs(avg_duration - target_duration) / 15.0
        duration_score = max(0, duration_score)
        
        toilet_score = (toilet_count / 10.0) * 0.6 + duration_score * 0.4
        raw_score += toilet_score * 2.0

    meds_submission = payload.get("meds") or []
    if not isinstance(meds_submission, list):
        meds_submission = []

    meds_list = load_meds_list()
    meds_groups = list(meds_list.keys())
    if len(meds_groups) >= 4:
        group1 = meds_groups[0]
        group2 = meds_groups[1]
        group3 = meds_groups[2]
        group4 = meds_groups[3]
    else:
        group1 = group2 = group3 = group4 = ""
    
    taken_cats = set()
    for med in meds_submission:
        med_name = med.get("name", "")
        for category, medicines in meds_list.items():
            if med_name in medicines:
                taken_cats.add(category)
                break
    
    target_99 = p["score_shift"] - math.log(1 / p["group1_target_prob"] - 1)
    target_60 = p["score_shift"] - math.log(1 / p["group2_target_prob"] - 1)
    
    if group1 in taken_cats:
        if raw_score < target_99:
            raw_score += (target_99 - raw_score)
    elif group2 in taken_cats:
        if raw_score < target_60:
            raw_score += (target_60 - raw_score)
    
    if group3 in taken_cats:
        raw_score *= p["group3_multiplier"]
    if group4 in taken_cats:
        raw_score += p["group4_add"]

    prob = sigmoid(raw_score - p["score_shift"])

    entry = {
        "date": today_str,
        "time": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "entry_time": dt.strftime("%Y-%m-%d %H:%M"),
        "gym": gym,
        "absent": absent,
        "pain": pain,
        "headache": headache,
        "tone_pressure": tone,
        "cough": cough,
        "toilet_times": cluster_time_entries(toilet_times_payload, window_minutes=60),
        "toilet": len(cluster_time_entries(toilet_times_payload, window_minutes=60)),
        "toilet_time_mean": 0.0,
        "toilet_duration_mean": 0.0,
        "raw_score": round(raw_score, 2),
        "final_prob": round(prob, 3),
        "meds": dedupe_meds_list(meds_submission, window_minutes=60),
        "notes": payload.get("notes", "")
    }

    udata.setdefault("history", []).append(entry)
    
    grouped = {}
    for h in udata["history"]:
        grouped.setdefault(h["date"], []).append(h)
    udata["history"] = sorted([collapse_entries_for_date(ents) for ents in grouped.values()], key=lambda x: x["date"])
    udata["input_count"] = len(udata["history"])
    udata["last_saved"] = datetime.utcnow().isoformat()
    
    save_individual(uid, udata)

    if prob >= LABEL_THRESHOLD:
        create_provisional(uid, dt, udata)

    evaluate_and_maybe_switch_base(uid, udata)
    update_cycle_on_observation(uid, dt.date(), prob, udata)
    optimize_params_for_uid(uid, udata)
    schedule_and_train_models_for_uid(uid, udata)
    
    changed = finalize_provisionals(uid, udata)
    if changed:
        udata["last_saved"] = datetime.utcnow().isoformat()
    
    save_individual(uid, udata)

    last_high_date = udata.get("last_high_prob_date", today_str)
    pred_res = fused_prediction_with_models(
        uid, 
        last_high_date, 
        float(udata.get("cycle_days", 28.0)), 
        udata.get("input_count", 0),
        udata
    )
    
    return entry, udata, pred_res

def add_entry_and_predict(uid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    entry, udata, pred_res = _compute_and_save_entry(uid, payload)
    return {
        "message": "予測完了",
        "uid": uid,
        "entry": entry,
        "prediction": pred_res,
        "individual": udata
    }

def add_entry_only(uid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    entry, udata, _ = _compute_and_save_entry(uid, payload)
    return {"message": "登録しました", "uid": uid, "entry": entry}

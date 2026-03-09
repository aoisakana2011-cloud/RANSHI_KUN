import math
from datetime import datetime, timedelta, date, time
from typing import Dict, Any, List, Optional

from .io import load_individual, save_individual, load_meds_list_raw
from .parsing import parse_datetime_str, time_weight_factor_from_timeobj, sigmoid
from .aggregation import aggregate_history_by_date, collapse_entries_for_date
from .ml import schedule_and_train_models_for_uid


POPULATION_CYCLE_DURATION_AVG = 5.0
PREDICTION_RANGE_DAYS = 60
LABEL_THRESHOLD = 0.6
HIGH_THRESHOLD = 0.84
MIN_STRONG_UPDATE_DAYS = 60
SCORE_PERIOD_DAYS = 5

GYM_WEIGHT_INIT = -4.0
ABSENT_WEIGHT_INIT = 2.0
PAIN_WEIGHT_INIT = 2.2
HEADACHE_WEIGHT_INIT = 1.5
TONE_WEIGHT_INIT = 1.0
FATIGUE_WEIGHT_INIT = 1.8
BLOATING_WEIGHT_INIT = 1.6
BREAST_TENDERNESS_WEIGHT_INIT = 1.4
PROB_CAP_MAX = 0.85
PROB_CAP_MIN = 0.20
COUGH_MAX_MULTIPLIER_INIT = 1.1
COUGH_MIN_MULTIPLIER_INIT = 0.3
GROUP1_TARGET_PROB_INIT = 0.95
GROUP2_TARGET_PROB_INIT = 0.55
GROUP3_MULTIPLIER_INIT = 0.4
GROUP4_ADD_INIT = 0.05
SCORE_SHIFT_INIT = 1.0


def _default_weights() -> Dict[str, float]:
    return {
        "gym": GYM_WEIGHT_INIT,
        "absent": ABSENT_WEIGHT_INIT,
        "pain": PAIN_WEIGHT_INIT,
        "headache": HEADACHE_WEIGHT_INIT,
        "tone": TONE_WEIGHT_INIT,
    }


def _default_params() -> Dict[str, float]:
    return {
        "cough_max_multiplier": COUGH_MAX_MULTIPLIER_INIT,
        "cough_min_multiplier": COUGH_MIN_MULTIPLIER_INIT,
        "group1_target_prob": GROUP1_TARGET_PROB_INIT,
        "group2_target_prob": GROUP2_TARGET_PROB_INIT,
        "group3_multiplier": GROUP3_MULTIPLIER_INIT,
        "group4_add": GROUP4_ADD_INIT,
        "score_shift": SCORE_SHIFT_INIT,
    }


def _create_default_individual(uid: str) -> Dict[str, Any]:
    now = datetime.utcnow()
    return {
        "uid": uid,
        "cycle_days": 28.0,
        "toilet_avg": 7.0,
        "toilet_duration_avg": 0.0,
        "input_count": 0,
        "last_high_prob_date": now.date().strftime("%Y-%m-%d"),
        "base_prob": 0.0,
        "base_start_date": "",
        "pending_candidate_start": None,
        "history": [],
        "toilet_time_mean": None,
        "provisional_periods": [],
        "last_saved": now.isoformat(),
        "models": {},
        "weights": _default_weights(),
        "params": _default_params(),
    }


def _score_sum_for_period(by_date: Dict[str, Dict[str, Any]], end_date: date, days: int = SCORE_PERIOD_DAYS) -> float:
    total = 0.0
    for i in range(0, days):
        d = (end_date - timedelta(days=i)).strftime("%Y-%m-%d")
        total += float(by_date.get(d, {}).get("final_prob", 0.0) or 0.0)
    return float(total)


def _evaluate_and_maybe_switch_base(uid: str) -> None:
    ind = load_individual(uid)
    if ind is None:
        return
    hist = ind.get("history", []) or []
    agg = aggregate_history_by_date(hist)
    if not agg:
        return
    dates = sorted(agg.keys())
    first_date = datetime.strptime(dates[0], "%Y-%m-%d").date()
    base_start = ind.get("base_start_date", None)
    base_prob = float(ind.get("base_prob", 0.0) or 0.0)
    pending = ind.get("pending_candidate_start", None)
    if not base_start:
        candidate = first_date
        candidate_score = _score_sum_for_period(
            agg, end_date=candidate + timedelta(days=SCORE_PERIOD_DAYS - 1), days=SCORE_PERIOD_DAYS
        )
        ind["base_start_date"] = candidate.strftime("%Y-%m-%d")
        ind["base_prob"] = float(candidate_score)
        ind["pending_candidate_start"] = None
        save_individual(uid, ind)
        return
    if pending:
        try:
            pending_date = datetime.strptime(pending, "%Y-%m-%d").date()
        except Exception:
            pending_date = None
        if pending_date:
            if datetime.utcnow().date() >= pending_date + timedelta(days=SCORE_PERIOD_DAYS - 1):
                candidate_score = _score_sum_for_period(
                    agg, end_date=pending_date + timedelta(days=SCORE_PERIOD_DAYS - 1), days=SCORE_PERIOD_DAYS
                )
                if candidate_score > base_prob:
                    ind["base_start_date"] = pending_date.strftime("%Y-%m-%d")
                    ind["base_prob"] = float(candidate_score)
                ind["pending_candidate_start"] = None
                save_individual(uid, ind)
                return
    try:
        base_start_date = datetime.strptime(ind.get("base_start_date", dates[0]), "%Y-%m-%d").date()
    except Exception:
        base_start_date = first_date
    for d in dates:
        d_date = datetime.strptime(d, "%Y-%m-%d").date()
        if base_start_date < d_date <= base_start_date + timedelta(days=16):
            if datetime.utcnow().date() >= d_date + timedelta(days=SCORE_PERIOD_DAYS - 1):
                candidate_score = _score_sum_for_period(
                    agg, end_date=d_date + timedelta(days=SCORE_PERIOD_DAYS - 1), days=SCORE_PERIOD_DAYS
                )
                if candidate_score > base_prob:
                    ind["base_start_date"] = d_date.strftime("%Y-%m-%d")
                    ind["base_prob"] = float(candidate_score)
                    ind["pending_candidate_start"] = None
                    save_individual(uid, ind)
                    return
            else:
                ind["pending_candidate_start"] = d_date.strftime("%Y-%m-%d")
                save_individual(uid, ind)
                return


def _adaptive_learning_rate(input_count: int, base_alpha: float = 0.30) -> float:
    if input_count < 10:
        return min(0.8, base_alpha * 2.5)
    elif input_count < 30:
        return min(0.6, base_alpha * 2.0)
    elif input_count < 60:
        return min(0.4, base_alpha * 1.3)
    else:
        return max(0.1, base_alpha * 0.8)


def _update_cycle_on_observation(uid: str, observed_date: date, observed_prob: float) -> None:
    if observed_prob < HIGH_THRESHOLD:
        return
    ind = load_individual(uid)
    if ind is None:
        return
    try:
        last_high = datetime.strptime(ind.get("last_high_prob_date", observed_date.strftime("%Y-%m-%d")), "%Y-%m-%d")
    except Exception:
        last_high = datetime.combine(observed_date, time.min)
    cycle = float(ind.get("cycle_days", 28.0) or 28.0)
    predicted_center = last_high + timedelta(days=cycle)
    shift = (datetime.combine(observed_date, time.min) - predicted_center).days
    input_count = int(ind.get("input_count", 0) or 0)
    
    alpha = _adaptive_learning_rate(input_count)
    
    new_cycle = (1 - alpha) * cycle + alpha * (cycle + shift)
    new_cycle = max(20.0, min(40.0, new_cycle))
    ind["cycle_days"] = float(new_cycle)
    ind["last_high_prob_date"] = observed_date.strftime("%Y-%m-%d")
    ind["last_observed_prob"] = float(observed_prob)
    ind["last_learning_rate"] = float(alpha)
    save_individual(uid, ind)


def _compute_day_period_probability(
    mu_date: date, sigma_days: float, target_date: date, days: int = SCORE_PERIOD_DAYS
) -> float:
    if isinstance(mu_date, datetime):
        mu = mu_date.date()
    else:
        mu = mu_date
    if isinstance(target_date, datetime):
        t = target_date.date()
    else:
        t = target_date
    half = days // 2
    a = (t - timedelta(days=half) - mu).days
    b = (t + timedelta(days=half) - mu).days
    if sigma_days <= 0:
        return 0.0
    z_a = a / float(sigma_days)
    z_b = b / float(sigma_days)
    cdf_a = 0.5 * (1.0 + math.erf(z_a / math.sqrt(2.0)))
    cdf_b = 0.5 * (1.0 + math.erf(z_b / math.sqrt(2.0)))
    prob = cdf_b - cdf_a
    prob = max(0.0, min(1.0, prob))
    return prob


def compute_prediction_distribution(
    last_high_date, cycle_days: float, input_count: int, days: int = PREDICTION_RANGE_DAYS, reference_date: Optional[date] = None
) -> Dict[str, Any]:
    if isinstance(last_high_date, str):
        try:
            last_high_date = datetime.strptime(last_high_date, "%Y-%m-%d")
        except Exception:
            last_high_date = datetime.utcnow()
    if isinstance(last_high_date, datetime):
        last_high = last_high_date
    else:
        last_high = datetime.combine(last_high_date, time.min)
    next_peak = last_high + timedelta(days=cycle_days)
    if reference_date is None:
        today = datetime.utcnow().date()
    else:
        today = reference_date.date() if isinstance(reference_date, datetime) else reference_date
    # 過去の last_high だと next_peak が昔になり全曜日同じ確率になるので、
    # 予測範囲内にピークが来るよう next_peak を進める（Ranshi_Kun の意図に合わせる）
    while next_peak.date() < today:
        next_peak = next_peak + timedelta(days=cycle_days)
    base_sigma = max(1.0, float(cycle_days) / 5.0)
    reduction_factor = min(1.0, float(input_count) / float(MIN_STRONG_UPDATE_DAYS or 1))
    sigma = max(1.0, base_sigma * (1.0 - 0.7 * reduction_factor))
    days = max(1, int(days))
    dates: List[date] = [today + timedelta(days=i) for i in range(0, days)]
    raw_probs: List[float] = []
    for d in dates:
        p = _compute_day_period_probability(next_peak.date(), sigma, d, days=SCORE_PERIOD_DAYS)
        raw_probs.append(p)
    raw = math.fsum(raw_probs)
    raw_arr = [float(v) for v in raw_probs]
    evidence_strength = min(0.95, 0.15 + 0.85 * (float(input_count) / float(max(1, MIN_STRONG_UPDATE_DAYS))))
    prior = 0.02
    combined = []
    for v in raw_arr:
        c = prior * (1.0 - evidence_strength) + v * evidence_strength
        c = max(0.0, min(0.9999, c))
        combined.append(c)
    s = sum(combined)
    if s > 0:
        combined = [v / s for v in combined]
    scaled = [v * 100.0 for v in combined]
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in dates],
        "percent": scaled,
        "sigma": float(sigma),
        "center": next_peak.strftime("%Y-%m-%d"),
        "raw": raw_arr,
    }


def add_entry_and_predict(uid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    entry, udata = _compute_and_save_entry(uid, payload)
    today_str = entry.get("date", "")
    try:
        last_high = udata.get("last_high_prob_date", today_str)
    except Exception:
        last_high = today_str
    cycle_days = float(udata.get("cycle_days", 28.0) or 28.0)
    input_count = int(udata.get("input_count", 0) or 0)

    # 元のRanshi_Kun.pyと同じ: 予測範囲は「今日」起点の60日（reference_date を渡さない）
    pred_res = compute_prediction_distribution(
        last_high, cycle_days, input_count, days=PREDICTION_RANGE_DAYS, reference_date=None
    )
    udata["_last_prediction"] = {
        "generated_at": datetime.utcnow().isoformat(),
        "center_date": pred_res.get("center"),
        "sigma": pred_res.get("sigma"),
        "range_days": PREDICTION_RANGE_DAYS,
        "dates": pred_res.get("dates"),
        "percent": pred_res.get("percent"),
    }
    save_individual(uid, udata)

    try:
        schedule_and_train_models_for_uid(uid)
    except Exception:
        pass

    return {
        "uid": uid,
        "entry": {
            "date": entry["date"],
            "raw_score": entry["raw_score"],
            "final_prob": entry["final_prob"],
        },
        "prediction": {
            "center_date": pred_res.get("center"),
            "sigma": pred_res.get("sigma"),
            "range_days": PREDICTION_RANGE_DAYS,
            "dates": pred_res.get("dates"),
            "percent": pred_res.get("percent"),
        },
    }


def _enhanced_sigmoid(x: float, shift: float = 0.0, steepness: float = 1.0) -> float:
    return 1.0 / (1.0 + math.exp(-steepness * (x - shift)))


def _calculate_medical_probability(raw_score: float, weights_sum: float, params: Dict[str, float], udata: Dict[str, Any]) -> float:
    base_prob = _enhanced_sigmoid(raw_score - params["score_shift"], steepness=0.6)
    
    gym_bonus = 0.0
    if weights_sum < 0:
        gym_bonus = min(0.15, abs(weights_sum) * 0.05)
    
    pain_bonus = 0.0
    if raw_score > 2.0:
        pain_bonus = min(0.20, (raw_score - 2.0) * 0.08)
    
    final_prob = base_prob + gym_bonus + pain_bonus
    
    input_count = len(udata.get("history", []))
    if input_count < 5:
        final_prob *= 0.5
    elif input_count < 10:
        final_prob *= 0.7
    elif input_count < 20:
        final_prob *= 0.85
    
    return min(0.90, max(0.0, final_prob))


def _predict_internal_factors(udata: Dict[str, Any]) -> Dict[str, Any]:
    history = udata.get("history", [])
    if len(history) < 5:
        return {
            "hormone_balance": 0.5,
            "estrogen_level": 0.5,
            "progesterone_level": 0.5,
            "cycle_phase": "unknown",
            "confidence": 0.1
        }
    
    recent_history = history[-10:]
    
    pain_avg = sum(entry.get("pain", 0) for entry in recent_history) / len(recent_history)
    headache_avg = sum(entry.get("headache", 0) for entry in recent_history) / len(recent_history)
    toilet_avg = sum(entry.get("toilet", 0) for entry in recent_history) / len(recent_history)
    gym_avg = sum(entry.get("gym", 0) for entry in recent_history) / len(recent_history)
    
    exercise_deficit = max(0, 3 - gym_avg) / 3
    
    symptom_score = (pain_avg + headache_avg) / 10
    
    toilet_score = min(1.0, toilet_avg / 10)
    
    hormone_balance = min(1.0, exercise_deficit * 0.4 + symptom_score * 0.4 + toilet_score * 0.2)
    
    estrogen_level = min(1.0, exercise_deficit * 0.3 + headache_avg * 0.2 + min(pain_avg, 3) * 0.3)
    
    progesterone_level = min(1.0, max(pain_avg - 2, 0) * 0.4 + toilet_score * 0.3)
    
    high_prob_days = [entry for entry in recent_history if entry.get("final_prob", 0) > 0.6]
    if len(high_prob_days) > 0:
        cycle_phase = "luteal" if hormone_balance > 0.6 else "follicular"
    else:
        cycle_phase = "menstrual" if pain_avg > 2 else "follicular"
    
    confidence = min(1.0, len(recent_history) / 20)
    
    return {
        "hormone_balance": round(hormone_balance, 3),
        "estrogen_level": round(estrogen_level, 3),
        "progesterone_level": round(progesterone_level, 3),
        "cycle_phase": cycle_phase,
        "confidence": round(confidence, 3),
        "predicted_at": datetime.utcnow().isoformat(),
        "data_points": len(recent_history)
    }


def _compute_and_save_entry(uid: str, payload: Dict[str, Any]) -> tuple:
    dt_str = payload.get("datetime") or payload.get("date")
    dt = parse_datetime_str(dt_str) if dt_str else None
    if dt is None:
        dt = datetime.utcnow()
    today_str = dt.date().strftime("%Y-%m-%d")
    entry_tf = time_weight_factor_from_timeobj(dt.time())

    udata = load_individual(uid) or _create_default_individual(uid)
    w = dict(_default_weights())
    w.update(udata.get("weights") or {})
    p = dict(_default_params())
    p.update(udata.get("params") or {})

    gym = int(payload.get("gym", 0) or 0)
    absent = int(payload.get("absent", 0) or 0)
    pain = int(payload.get("pain", 0) or 0)
    headache = int(payload.get("headache", 0) or 0)
    tone = int(payload.get("tone_pressure", payload.get("tone", 0) or 0))
    cough = int(payload.get("cough", 0) or 0)

    weighted_score = (
        w["gym"] * gym
        + w["absent"] * absent
        + w["pain"] * pain
        + w["headache"] * headache
        + w["tone"] * tone
    )
    
    weights_sum = w["gym"] * gym
    
    raw_score = weighted_score * entry_tf

    cough_multiplier = p["cough_max_multiplier"] - (p["cough_max_multiplier"] - p["cough_min_multiplier"]) * (cough / 4.0)
    raw_score *= cough_multiplier

    meds_submission = payload.get("meds") or []
    if not isinstance(meds_submission, list):
        meds_submission = []

    CAT_PERIOD_ONLY = "生理のときにしかほぼ使わない薬"
    CAT_DUAL_USE = "日用でも生理でも使う薬"
    CAT_POLLEN = "花粉症の薬"
    taken_cats = set(m.get("category") for m in meds_submission if isinstance(m, dict) and m.get("category"))

    if CAT_POLLEN in taken_cats:
        raw_score *= 0.5
    
    prob = _calculate_medical_probability(raw_score, weights_sum, p, udata)
    
    if CAT_PERIOD_ONLY in taken_cats:
        prob = 0.99
    elif CAT_DUAL_USE in taken_cats:
        prob = min(1.0, prob + 0.30)

    input_count_before = int(udata.get("input_count", 0) or 0)
    cap = PROB_CAP_MIN + (PROB_CAP_MAX - PROB_CAP_MIN) * min(1.0, input_count_before / max(1, MIN_STRONG_UPDATE_DAYS))
    prob = min(float(prob), cap)

    toilet_times_payload = payload.get("toilet_times") or []
    toilet_times: List[Dict[str, Any]] = []
    for t in toilet_times_payload:
        if isinstance(t, dict) and t.get("time"):
            toilet_times.append({"time": t.get("time"), "duration_min": int(t.get("duration_min", 0) or 0)})

    entry = {
        "date": today_str,
        "time": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "entry_time": dt.strftime("%Y-%m-%d %H:%M"),
        "gym": gym, "absent": absent, "pain": pain, "headache": headache,
        "tone_pressure": tone, "cough": cough,
        "toilet_times": toilet_times, "toilet": len(toilet_times),
        "raw_score": round(float(raw_score), 2), "final_prob": round(float(prob), 3),
        "meds": meds_submission,
        "notes": (payload.get("notes") or "").strip() if isinstance(payload.get("notes"), str) else "",
    }

    history = list(udata.get("history", []))
    history.append(entry)
    from collections import defaultdict
    by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for h in history:
        d = h.get("date")
        if d:
            by_date[d].append(h)
    collapsed = []
    for d in sorted(by_date.keys()):
        ents = by_date[d]
        if len(ents) == 1:
            collapsed.append(ents[0])
        else:
            c = collapse_entries_for_date(ents)
            collapsed.append({
                "date": d, "time": ents[-1].get("time", ""), "entry_time": ents[-1].get("entry_time", ""),
                "gym": c.get("gym", 0), "absent": c.get("absent", 0), "pain": c.get("pain", 0),
                "headache": c.get("headache", 0), "tone_pressure": c.get("tone", 0), "cough": c.get("cough", 0),
                "toilet_times": c.get("toilet_times", []), "toilet": c.get("toilet_count", 0),
                "raw_score": round(c.get("raw_score", 0), 2), "final_prob": round(c.get("final_prob", 0), 3),
                "meds": c.get("meds", []),
                "notes": "; ".join((e.get("notes") or "").strip() for e in ents if e.get("notes")).strip() or None,
            })
    udata["history"] = collapsed
    udata["input_count"] = len(collapsed)
    udata["last_saved"] = datetime.utcnow().isoformat()
    
    internal_predictions = _predict_internal_factors(udata)
    udata["internal_predictions"] = internal_predictions
    
    save_individual(uid, udata)

    if prob >= LABEL_THRESHOLD:
        _evaluate_and_maybe_switch_base(uid)
    _update_cycle_on_observation(uid, dt.date(), float(prob))
    try:
        schedule_and_train_models_for_uid(uid)
    except Exception:
        pass
    return entry, load_individual(uid) or udata


def add_entry_only(uid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    entry, _ = _compute_and_save_entry(uid, payload)
    return {"message": "登録しました", "uid": uid, "entry": {"date": entry["date"], "raw_score": entry["raw_score"], "final_prob": entry["final_prob"]}}


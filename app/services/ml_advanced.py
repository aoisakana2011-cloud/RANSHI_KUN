import os
import json
import math
import numpy as np
from datetime import datetime, timedelta, time, date
from typing import Dict, List, Any, Tuple, Optional
from scipy.optimize import minimize
from sklearn.metrics import log_loss
import joblib

# 定数
POPULATION_CYCLE_DURATION_AVG = 5.0
PREDICTION_RANGE_DAYS = 60
LABEL_THRESHOLD = 0.6
HIGH_THRESHOLD = 0.84
MIN_STRONG_UPDATE_DAYS = 90
SCORE_PERIOD_DAYS = 5
PROVISIONAL_PERIOD_DAYS = 5
PROVISIONAL_COMPARISON_DAYS = 20
PROVISIONAL_CONFIDENCE_SCALE = 4.0
EPS = 1e-6

# 重み初期値
GYM_WEIGHT_INIT = 3.5 
ABSENT_WEIGHT_INIT = 1.0 
PAIN_WEIGHT_INIT = 1.2
HEADACHE_WEIGHT_INIT = 1.0
TONE_WEIGHT_INIT = 0.5
COUGH_MAX_MULTIPLIER_INIT = 1.2
COUGH_MIN_MULTIPLIER_INIT = 0.2
GROUP1_TARGET_PROB_INIT = 0.99
GROUP2_TARGET_PROB_INIT = 0.60
GROUP3_MULTIPLIER_INIT = 0.5
GROUP4_ADD_INIT = 0.1
SCORE_SHIFT_INIT = 4.0

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))

def time_to_minutes(t):
    return t.hour * 60 + t.minute + t.second / 60.0

def minutes_to_time(minutes):
    m = int(round(minutes))
    h = (m // 60) % 24
    mm = m % 60
    return time(hour=h, minute=mm)

def time_weight_factor_from_timeobj(tobj):
    h = tobj.hour
    if 22 <= h or h < 6:
        return 1.45
    if 18 <= h < 22:
        return 1.20
    if 12 <= h < 18:
        return 1.05
    return 1.0

def aggregate_history_by_date(history):
    by_date = {}
    for h in history:
        d = h.get("date", "")
        if not d:
            continue
        if d not in by_date:
            by_date[d] = {"count": 0,"gym": 0.0,"absent": 0.0,"pain": 0.0,"headache": 0.0,"tone": 0.0,"toilet": 0.0,"toilet_time_mean": 0.0,"toilet_duration_mean": 0.0,"raw_score": 0.0,"final_prob": 0.0,"meds_count": 0, "cough": 0.0}
        e = by_date[d]
        e["count"] += 1
        e["gym"] += float(h.get("gym", 0))
        e["absent"] += float(h.get("absent", 0))
        e["pain"] += float(h.get("pain", 0))
        e["headache"] += float(h.get("headache", 0))
        e["tone"] += float(h.get("tone_pressure", 0))
        e["toilet"] += float(h.get("toilet", 0))
        e["toilet_time_mean"] += float(h.get("toilet_time_mean", 0.0))
        e["toilet_duration_mean"] += float(h.get("toilet_duration_mean", 0.0))
        e["raw_score"] += float(h.get("raw_score", 0.0))
        e["final_prob"] += float(h.get("final_prob", 0.0))
        e["cough"] += float(h.get("cough", 0))
        meds = h.get("meds", []) or []
        e["meds_count"] += len(meds)
    for d, v in list(by_date.items()):
        c = v["count"]
        if c > 0:
            v["gym"] /= c
            v["absent"] /= c
            v["pain"] /= c
            v["headache"] /= c
            v["tone"] /= c
            v["toilet"] /= c
            v["toilet_time_mean"] /= c
            v["toilet_duration_mean"] /= c
            v["raw_score"] /= c
            v["final_prob"] /= c
            v["cough"] /= c
            v["meds_count"] = int(round(v["meds_count"] / c))
    return by_date

def score_sum_for_period(by_date, end_date=None, days=SCORE_PERIOD_DAYS):
    if end_date is None:
        end_date = datetime.now().date()
    total = 0.0
    for i in range(0, days):
        d = (end_date - timedelta(days=i)).strftime("%Y-%m-%d")
        total += float(by_date.get(d, {}).get("final_prob", 0.0))
    return total

def compute_day_period_probability(mu_date, sigma_days, target_date, days=SCORE_PERIOD_DAYS):
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

def compute_prediction_distribution(last_high_date, cycle_days, input_count, days=PREDICTION_RANGE_DAYS, reference_date=None):
    if isinstance(last_high_date, str):
        try:
            last_high_date = datetime.strptime(last_high_date, "%Y-%m-%d")
        except Exception:
            last_high_date = datetime.now()
    if isinstance(last_high_date, datetime):
        last_high = last_high_date
    else:
        last_high = datetime.combine(last_high_date, time.min)
    next_peak = last_high + timedelta(days=cycle_days)
    base_sigma = max(1.0, float(cycle_days) / 5.0)
    reduction_factor = min(1.0, float(input_count) / float(MIN_STRONG_UPDATE_DAYS))
    sigma = max(1.0, base_sigma * (1.0 - 0.7 * reduction_factor))
    if reference_date is None:
        today = datetime.now().date()
    else:
        if isinstance(reference_date, datetime):
            today = reference_date.date()
        else:
            today = reference_date
    dates = [today + timedelta(days=i) for i in range(0, max(1, int(days)))]
    raw_probs = []
    for d in dates:
        p = compute_day_period_probability(next_peak.date(), sigma, d, days=SCORE_PERIOD_DAYS)
        raw_probs.append(p)
    raw = np.array(raw_probs, dtype=float)
    evidence_strength = min(0.95, 0.15 + 0.85 * (float(input_count) / float(max(1, MIN_STRONG_UPDATE_DAYS))))
    prior = 0.02
    combined = prior * (1.0 - evidence_strength) + raw * evidence_strength
    combined = np.clip(combined, 0.0, 0.9999)
    if combined.sum() > 0:
        combined = combined / combined.sum()
    scaled = combined * 100.0
    return {"dates": [d.strftime("%Y-%m-%d") for d in dates], "percent": scaled.tolist(), "sigma": sigma, "center": next_peak.strftime("%Y-%m-%d"), "raw": raw.tolist()}

def cluster_time_entries(toilet_entries, window_minutes=60):
    if not toilet_entries:
        return []
    sorted_entries = sorted(toilet_entries, key=lambda x: time_to_minutes(datetime.strptime(x["time"], "%H:%M").time()))
    clusters = []
    current_cluster = [sorted_entries[0]]
    for entry in sorted_entries[1:]:
        last_time = time_to_minutes(datetime.strptime(current_cluster[-1]["time"], "%H:%M").time())
        curr_time = time_to_minutes(datetime.strptime(entry["time"], "%H:%M").time())
        if curr_time - last_time <= window_minutes:
            current_cluster.append(entry)
        else:
            clusters.append(current_cluster)
            current_cluster = [entry]
    if current_cluster:
        clusters.append(current_cluster)
    clustered = []
    for cl in clusters:
        times = [datetime.strptime(e["time"], "%H:%M").time() for e in cl]
        mean_min = np.mean([time_to_minutes(t) for t in times])
        mean_time = minutes_to_time(mean_min)
        total_dur = sum(int(e.get("duration_min", 0)) for e in cl)
        clustered.append({"time": mean_time.strftime("%H:%M"), "duration_min": total_dur})
    return clustered

def dedupe_meds_list(meds, window_minutes=60):
    if not meds:
        return []
    sorted_meds = sorted(meds, key=lambda x: time_to_minutes(datetime.strptime(x["time"], "%H:%M").time()))
    unique = []
    seen = set()
    for m in sorted_meds:
        key = (m["name"].lower(), m.get("note", "").lower())
        if key in seen:
            continue
        unique.append(m)
        seen.add(key)
    return unique

def collapse_entries_for_date(entries_for_date):
    if not entries_for_date:
        return None
    gyms = [float(e.get("gym", 0)) for e in entries_for_date]
    absents = [float(e.get("absent", 0)) for e in entries_for_date]
    pains = [float(e.get("pain", 0)) for e in entries_for_date]
    heads = [float(e.get("headache", 0)) for e in entries_for_date]
    tones = [float(e.get("tone_pressure", 0)) for e in entries_for_date]
    coughs = [float(e.get("cough", 0)) for e in entries_for_date]
    raw_scores = [float(e.get("raw_score", 0.0)) for e in entries_for_date]
    final_probs = [float(e.get("final_prob", 0.0)) for e in entries_for_date]
    toilet_times_all = []
    toilet_durations = []
    meds_all = []
    notes = []
    for e in entries_for_date:
        toilet_times_all.extend(e.get("toilet_times", []))
        toilet_durations.extend([int(tt.get("duration_min", 0)) for tt in e.get("toilet_times", [])])
        meds_all.extend(e.get("meds", []))
        if e.get("notes"):
            notes.append(e.get("notes"))
    clustered = cluster_time_entries(toilet_times_all, window_minutes=60)
    toilet_count = len(clustered)
    toilet_time_mean = np.mean([time_to_minutes(datetime.strptime(t.get("time"), "%H:%M").time()) for t in clustered]) if clustered else 0.0
    toilet_duration_mean = float(np.mean(toilet_durations)) if toilet_durations else 0.0
    meds_dedup = dedupe_meds_list(meds_all, window_minutes=60)
    merged = {
        "date": entries_for_date[0].get("date"),
        "time": entries_for_date[-1].get("time"),
        "entry_time": entries_for_date[-1].get("entry_time"),
        "gym": float(np.mean(gyms)) if gyms else 0.0,
        "absent": float(np.mean(absents)) if absents else 0.0,
        "pain": float(np.mean(pains)) if pains else 0.0,
        "headache": float(np.mean(heads)) if heads else 0.0,
        "tone_pressure": float(np.mean(tones)) if tones else 0.0,
        "cough": float(np.mean(coughs)) if coughs else 0.0,
        "toilet_times": clustered,
        "toilet": int(round(toilet_count)),
        "toilet_time_mean": float(toilet_time_mean),
        "toilet_duration_mean": float(toilet_duration_mean),
        "raw_score": float(np.mean(raw_scores)),
        "final_prob": float(np.mean(final_probs)),
        "meds": meds_dedup,
        "notes": "; ".join(notes)
    }
    return merged

def extract_features_from_history(history, window_days=21):
    agg = aggregate_history_by_date(history)
    dates = sorted(agg.keys())
    X = []
    dates_parsed = []
    for d in dates:
        v = agg[d]
        feat = [
            v.get("toilet", 0.0),
            v.get("toilet_time_mean", 0.0) if v.get("toilet_time_mean") is not None else 0.0,
            v.get("toilet_duration_mean", 0.0),
            v.get("pain", 0.0),
            v.get("headache", 0.0),
            v.get("tone", 0.0),
            v.get("gym", 0.0),
            v.get("absent", 0.0),
            v.get("meds_count", 0),
            v.get("raw_score", 0.0),
            v.get("final_prob", 0.0),
            v.get("cough", 0.0)
        ]
        X.append(feat)
        dates_parsed.append(datetime.strptime(d, "%Y-%m-%d").date())
    if not X:
        return np.zeros((0,12)), []
    X = np.array(X, dtype=float)
    means = X.mean(axis=0)
    stds = X.std(axis=0) + 1e-6
    Xn = (X - means) / stds
    return Xn, dates_parsed

def generate_pseudo_labels_from_hmm_and_cp(history):
    X, dates = extract_features_from_history(history)
    if X.shape[0] == 0:
        return [], []
    
    labels = np.zeros(len(dates), dtype=int)
    confidences = np.zeros(len(dates), dtype=float)
    date_to_idx = {d: i for i, d in enumerate(dates)}
    
    agg = aggregate_history_by_date(history)
    for i, d in enumerate(dates):
        p = agg.get(d.strftime("%Y-%m-%d"), {}).get("final_prob", 0.0)
        if p >= LABEL_THRESHOLD:
            labels[i] = 1
            confidences[i] = max(confidences[i], min(0.9, p))
            
    return labels.tolist(), confidences.tolist()

def optimize_params_for_uid(uid, udata):
    history = udata.get("history", [])
    if len(history) < 10:
        return
    X, dates = extract_features_from_history(history)
    labels, _ = generate_pseudo_labels_from_hmm_and_cp(history)
    labels = np.array(labels)
    if labels.sum() < 3:
        return
    
    feat_indices = [6, 7, 3, 4, 5]
    score_feats = X[:, feat_indices]
    coughs = X[:, 11] 
    
    p = udata.get("params", {
        "cough_max_multiplier": COUGH_MAX_MULTIPLIER_INIT, 
        "cough_min_multiplier": COUGH_MIN_MULTIPLIER_INIT, 
        "group1_target_prob": GROUP1_TARGET_PROB_INIT, 
        "group2_target_prob": GROUP2_TARGET_PROB_INIT, 
        "group3_multiplier": GROUP3_MULTIPLIER_INIT, 
        "group4_add": GROUP4_ADD_INIT, 
        "score_shift": SCORE_SHIFT_INIT
    })
    w = udata.get("weights", {
        "gym": GYM_WEIGHT_INIT, 
        "absent": ABSENT_WEIGHT_INIT, 
        "pain": PAIN_WEIGHT_INIT, 
        "headache": HEADACHE_WEIGHT_INIT, 
        "tone": TONE_WEIGHT_INIT
    })
    
    def loss(params):
        w_arr = params[:5]
        cough_max, cough_min, g1_prob, g2_prob, g3_mult, g4_add, score_shift = params[5:]
        scores = np.dot(score_feats, w_arr)
        cough_mult = cough_max - (cough_max - cough_min) * (coughs / 4.0)
        scores *= cough_mult
        adj = np.ones_like(scores) 
        scores += adj
        probs = 1 / (1 + np.exp(-(scores - score_shift)))
        return log_loss(labels, probs)
    
    initial_params = np.array([
        w["gym"], w["absent"], w["pain"], w["headache"], w["tone"], 
        p["cough_max_multiplier"], p["cough_min_multiplier"], 
        p["group1_target_prob"], p["group2_target_prob"], 
        p["group3_multiplier"], p["group4_add"], p["score_shift"]
    ])
    
    res = minimize(loss, initial_params, method='BFGS')
    if res.success:
        new_params = res.x
        udata["weights"] = {
            "gym": float(new_params[0]), 
            "absent": float(new_params[1]), 
            "pain": float(new_params[2]), 
            "headache": float(new_params[3]), 
            "tone": float(new_params[4])
        }
        udata["params"] = {
            "cough_max_multiplier": float(new_params[5]), 
            "cough_min_multiplier": float(new_params[6]), 
            "group1_target_prob": float(new_params[7]), 
            "group2_target_prob": float(new_params[8]), 
            "group3_multiplier": float(new_params[9]), 
            "group4_add": float(new_params[10]), 
            "score_shift": float(new_params[11])
        }

def create_provisional(uid, start_date, udata):
    if isinstance(start_date, datetime):
        s = start_date.date()
    else:
        s = start_date
    end = s + timedelta(days=PROVISIONAL_PERIOD_DAYS-1)
    prov = {
        "id": f"prov_{s.strftime('%Y%m%d')}_{int(datetime.now().timestamp())}",
        "start_date": s.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "created_at": datetime.now().isoformat(),
        "status": "active",
        "score": None
    }
    udata.setdefault("provisional_periods", []).append(prov)
    udata["last_saved"] = datetime.now().isoformat()
    return prov

def _parse_ymd(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

def provisional_confidence(new_score, prev_score):
    rel = (float(new_score) - float(prev_score)) / max(float(prev_score), EPS)
    val = 1.0 / (1.0 + math.exp(-PROVISIONAL_CONFIDENCE_SCALE * rel))
    return float(val)

def apply_cycle_update_from_provisional(ind, new_prov, prev_prov):
    try:
        new_score = float(new_prov.get("score", 0.0))
    except Exception:
        new_score = 0.0
    try:
        prev_score = float(prev_prov.get("score", 0.0)) if prev_prov else 0.0
    except Exception:
        prev_score = 0.0
    conf = provisional_confidence(new_score, prev_score)
    input_count = ind.get("input_count", 0)
    if input_count < MIN_STRONG_UPDATE_DAYS:
        base_alpha = 0.0
    else:
        base_alpha = 0.30
    alpha = min(0.5, base_alpha + 0.2 * conf)
    try:
        last_high = datetime.strptime(ind.get("last_high_prob_date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d")
    except Exception:
        last_high = datetime.now()
    cycle = float(ind.get("cycle_days", 28.0))
    obs_date = _parse_ymd(new_prov.get("start_date"))
    if obs_date is None:
        return
    predicted_center = last_high + timedelta(days=cycle)
    shift = (obs_date - predicted_center).days
    new_cycle = (1 - alpha) * cycle + alpha * (cycle + shift)
    new_cycle = max(20.0, min(40.0, new_cycle))
    ind["cycle_days"] = float(new_cycle)
    if conf > 0.6:
        ind["last_high_prob_date"] = obs_date.strftime("%Y-%m-%d")
    new_prov["confidence"] = conf

def finalize_provisionals(uid, udata):
    hist = udata.get("history", [])
    agg = aggregate_history_by_date(hist)
    today = datetime.now().date()
    provs = udata.setdefault("provisional_periods", [])
    changed = False
    for p in sorted(provs, key=lambda x: x.get("start_date", "")):
        if p.get("status") != "active":
            continue
        end = _parse_ymd(p.get("end_date"))
        if end is None:
            continue
        if end < today:
            score_new = score_sum_for_period(agg, end_date=end, days=SCORE_PERIOD_DAYS)
            p["score"] = float(score_new)
            start = _parse_ymd(p.get("start_date"))
            prev = None
            prev_start_limit = start - timedelta(days=PROVISIONAL_COMPARISON_DAYS)
            candidates = [q for q in provs if q.get("id") != p.get("id")]
            cand_parsed = []
            for q in candidates:
                qs = _parse_ymd(q.get("start_date"))
                if qs and prev_start_limit <= qs < start:
                    cand_parsed.append((qs, q))
            if cand_parsed:
                prev = sorted(cand_parsed, key=lambda x: x[0], reverse=True)[0][1]
            if prev is None:
                p["status"] = "finalized"
                changed = True
                apply_cycle_update_from_provisional(udata, p, None)
            else:
                prev_end = _parse_ymd(prev.get("end_date"))
                if prev.get("score") is None and prev_end is not None:
                    prev["score"] = float(score_sum_for_period(agg, end_date=prev_end, days=SCORE_PERIOD_DAYS))
                try:
                    new_s = float(p["score"])
                    prev_s = float(prev.get("score", 0.0))
                    if new_s > prev_s:
                        prev["status"] = "discarded"
                        p["status"] = "finalized"
                        changed = True
                        apply_cycle_update_from_provisional(udata, p, prev)
                    else:
                        p["status"] = "discarded"
                        changed = True
                except Exception:
                    p["status"] = "finalized"
                    changed = True
    return changed

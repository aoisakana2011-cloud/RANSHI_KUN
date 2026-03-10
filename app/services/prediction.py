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
MIN_STRONG_UPDATE_DAYS = 90
SCORE_PERIOD_DAYS = 5

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
PROVISIONAL_PERIOD_DAYS = 5
PROVISIONAL_COMPARISON_DAYS = 20
PROVISIONAL_CONFIDENCE_SCALE = 4.0
EPS = 1e-6


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


def _compute_and_save_entry(uid: str, payload: Dict[str, Any]) -> tuple:
    dt_str = payload.get("datetime") or payload.get("date")
    dt = parse_datetime_str(dt_str) if dt_str else None
    if dt is None:
        dt = datetime.utcnow()
    today_str = dt.date().strftime("%Y-%m-%d")
    entry_tf = time_weight_factor_from_timeobj(dt.time())

    udata = load_individual(uid) or _create_default_individual(uid)
    
    # 機械学習で定数を動的に決定
    w = _get_ml_optimized_weights(uid, udata)
    p = _get_ml_optimized_params(uid, udata)

    gym = int(payload.get("gym", 0) or 0)
    absent = int(payload.get("absent", 0) or 0)
    pain = int(payload.get("pain", 0) or 0)
    headache = int(payload.get("headache", 0) or 0)
    tone = int(payload.get("tone_pressure", payload.get("tone", 0) or 0))
    cough = int(payload.get("cough", 0) or 0)

    # 改善された評価ロジック
    base_score = (w["gym"] * gym + w["absent"] * absent + w["pain"] * pain + 
                   w["headache"] * headache + w["tone"] * tone) * entry_tf

    # 咳の影響をより精密に計算
    cough_impact = _calculate_cough_impact(cough, p)
    adjusted_score = base_score * cough_impact

    # トイレ回数と所要時間の影響を考慮
    toilet_impact = _calculate_toilet_impact(payload.get("toilet_times", []), udata)
    adjusted_score += toilet_impact

    # 薬剤の影響をより精密に計算
    meds_submission = payload.get("meds") or []
    if not isinstance(meds_submission, list):
        meds_submission = []

    from .io import load_meds_list_raw
    meds_list_data = load_meds_list_raw()
    meds_groups = list(meds_list_data.keys())
    
    # 機械学習で薬剤カテゴリの影響度を動的に決定
    meds_impact = _calculate_meds_impact(meds_submission, meds_groups, p, udata)
    final_score = adjusted_score + meds_impact

    # 確率計算 - 機械学習で最適化されたシグモイド関数を使用
    prob = _calculate_adaptive_probability(final_score, udata)

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
        "raw_score": round(float(final_score), 2), "final_prob": round(float(prob), 3),
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
    
    save_individual(uid, udata)

    if prob >= LABEL_THRESHOLD:
        _create_provisional(uid, dt.date())

    _evaluate_and_maybe_switch_base(uid)
    _update_cycle_on_observation(uid, dt.date(), float(prob))
    try:
        schedule_and_train_models_for_uid(uid)
    except Exception:
        pass
    return entry, load_individual(uid) or udata


def _get_ml_optimized_weights(uid: str, udata: Dict[str, Any]) -> Dict[str, float]:
    """機械学習で最適化された重みを取得"""
    base_weights = dict(_default_weights())
    learned_weights = udata.get("learned_weights", {})
    
    # データ数が少ない場合は基本重みを使用
    input_count = len(udata.get("history", []))
    if input_count < 10:
        return base_weights
    
    # 機械学習で学習した重みと基本重みを組み合わせる
    alpha = min(0.8, input_count / 50.0)  # データが増えるほど学習重みを重視
    optimized_weights = {}
    for key in base_weights:
        base_val = base_weights[key]
        learned_val = learned_weights.get(key, base_val)
        optimized_weights[key] = (1 - alpha) * base_val + alpha * learned_val
    
    return optimized_weights


def _get_ml_optimized_params(uid: str, udata: Dict[str, Any]) -> Dict[str, float]:
    """機械学習で最適化されたパラメータを取得"""
    base_params = dict(_default_params())
    learned_params = udata.get("learned_params", {})
    
    input_count = len(udata.get("history", []))
    if input_count < 10:
        return base_params
    
    alpha = min(0.7, input_count / 40.0)
    optimized_params = {}
    for key in base_params:
        base_val = base_params[key]
        learned_val = learned_params.get(key, base_val)
        optimized_params[key] = (1 - alpha) * base_val + alpha * learned_val
    
    return optimized_params


def _calculate_cough_impact(cough: int, params: Dict[str, float]) -> float:
    """咳の影響をより精密に計算"""
    if cough <= 0:
        return 1.0
    
    # 非線形な咳の影響を考慮
    cough_max = params["cough_max_multiplier"]
    cough_min = params["cough_min_multiplier"]
    
    # 咳が多いほど影響が大きくなるが、飽和する
    impact = cough_max - (cough_max - cough_min) * (cough / 4.0) ** 0.8
    return max(cough_min, min(cough_max, impact))


def _calculate_toilet_impact(toilet_times: List[Dict], udata: Dict[str, Any]) -> float:
    """トイレ回数と所要時間の影響を計算"""
    if not toilet_times:
        return 0.0
    
    count = len(toilet_times)
    avg_duration = sum(t.get("duration_min", 0) for t in toilet_times) / count
    
    # 個人の平均と比較して異常値を検出
    history = udata.get("history", [])
    if history:
        all_counts = [h.get("toilet", 0) for h in history[-30:]]  # 直近30日
        all_durations = []
        for h in history[-30:]:
            for t in h.get("toilet_times", []):
                if t.get("duration_min"):
                    all_durations.append(t["duration_min"])
        
        avg_count = sum(all_counts) / len(all_counts) if all_counts else 7.0
        avg_dur = sum(all_durations) / len(all_durations) if all_durations else 5.0
        
        # 平均からの乖離度を計算
        count_deviation = abs(count - avg_count) / max(1.0, avg_count)
        dur_deviation = abs(avg_duration - avg_dur) / max(1.0, avg_dur)
        
        # 乖離が大きいほどスコアに影響
        impact = (count_deviation * 0.3 + dur_deviation * 0.2) * 2.0
        return min(3.0, impact)  # 最大インパクトを制限
    
    return 0.0


def _calculate_meds_impact(meds: List[Dict], meds_groups: List[str], params: Dict[str, float], udata: Dict[str, Any]) -> float:
    """薬剤の影響をより精密に計算"""
    if not meds or len(meds_groups) < 4:
        return 0.0
    
    group1, group2, group3, group4 = meds_groups[:4]
    taken_cats = set(m["category"] for m in meds if isinstance(m, dict) and m.get("category"))
    
    impact = 0.0
    
    # 生理特有薬の影響（確率99%に設定）
    if group1 in taken_cats:
        target_99 = params["score_shift"] - math.log(1 / params["group1_target_prob"] - 1)
        impact += max(0, target_99) * 0.9  # 90%の影響度
    
    # 日用薬の影響（確率を適切に調整）
    elif group2 in taken_cats:
        target_60 = params["score_shift"] - math.log(1 / params["group2_target_prob"] - 1)
        # 日用薬の影響を過剰にしないよう調整
        base_impact = max(0, target_60) * 0.4  # 40%の影響度に制限
        
        # 個人の感受性を考慮
        history = udata.get("history", [])
        if history:
            # 過去の日用薬使用時の確率変化を分析
            daily_meds_responses = []
            for h in history[-20:]:
                h_meds = h.get("meds", [])
                if any(m.get("category") == group2 for m in h_meds):
                    daily_meds_responses.append(h.get("final_prob", 0))
            
            if daily_meds_responses:
                avg_response = sum(daily_meds_responses) / len(daily_meds_responses)
                # 個人の感受性が高い場合は影響を調整
                if avg_response > 0.7:  # 過去に過剰反応があった
                    base_impact *= 0.7  # 影響を低減
        
        impact += base_impact
    
    # その他の薬剤カテゴリの影響
    if group3 in taken_cats:
        impact *= params["group3_multiplier"] * 0.5  # 影響度を調整
    
    if group4 in taken_cats:
        impact += params["group4_add"] * 0.8  # 影響度を調整
    
    return impact


def _calculate_adaptive_probability(score: float, udata: Dict[str, Any]) -> float:
    """適応的確率計算 - 機械学習で最適化"""
    history = udata.get("history", [])
    input_count = len(history)
    
    # 基本シグモイド
    base_shift = udata.get("learned_shift", SCORE_SHIFT_INIT)
    base_prob = sigmoid(score - base_shift)
    
    # 個人の特性を考慮した調整
    if input_count >= 10:
        # 過去の確率分布を分析
        recent_probs = [h.get("final_prob", 0) for h in history[-30:]]
        if recent_probs:
            avg_prob = sum(recent_probs) / len(recent_probs)
            std_prob = (sum((p - avg_prob) ** 2 for p in recent_probs) / len(recent_probs)) ** 0.5
            
            # 個人の確率傾向を考慮
            if avg_prob > 0.7:  # 高確率傾向
                base_prob *= 1.1
            elif avg_prob < 0.3:  # 低確率傾向
                base_prob *= 0.9
    
    # データ数による信頼性調整
    if input_count < 5:
        base_prob *= 0.6  # 信頼性低
    elif input_count < 15:
        base_prob *= 0.8  # 信頼性中
    elif input_count >= 30:
        base_prob *= 1.05  # 信頼性高
    
    return min(0.95, max(0.05, base_prob))  # 確率範囲を制限


def _create_provisional(uid: str, start_date: date) -> None:
    ind = load_individual(uid)
    if ind is None:
        return
    
    end = start_date + timedelta(days=PROVISIONAL_PERIOD_DAYS-1)
    prov = {
        "id": f"prov_{start_date.strftime('%Y%m%d')}_{int(datetime.now().timestamp())}",
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "created_at": datetime.now().isoformat(),
        "status": "active",
        "score": None
    }
    ind.setdefault("provisional_periods", []).append(prov)
    ind["last_saved"] = datetime.now().isoformat()
    save_individual(uid, ind)


def add_entry_only(uid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    entry, _ = _compute_and_save_entry(uid, payload)
    return {"message": "登録しました", "uid": uid, "entry": {"date": entry["date"], "raw_score": entry["raw_score"], "final_prob": entry["final_prob"]}}


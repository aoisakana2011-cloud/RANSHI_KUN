from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from ..extensions import db
from ..models import ProvisionalPeriod

PROVISIONAL_PERIOD_DAYS = 5
PROVISIONAL_COMPARISON_DAYS = 20
PROVISIONAL_CONFIDENCE_SCALE = 4.0
EPS = 1e-6

def _parse_ymd(s: Optional[str]):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

def provisional_confidence(new_score: float, prev_score: float) -> float:
    rel = (float(new_score) - float(prev_score)) / max(float(prev_score), EPS)
    import math
    val = 1.0 / (1.0 + math.exp(-PROVISIONAL_CONFIDENCE_SCALE * rel))
    return float(val)

def create_provisional(individual_id: int, start_date) -> ProvisionalPeriod:
    if isinstance(start_date, str):
        start = _parse_ymd(start_date)
    else:
        start = start_date
    end = start + timedelta(days=PROVISIONAL_PERIOD_DAYS - 1)
    prov_id = f"prov_{start.strftime('%Y%m%d')}_{int(datetime.utcnow().timestamp())}"
    p = ProvisionalPeriod(individual_id=individual_id, prov_id=prov_id, start_date=start, end_date=end, status="active", created_at=datetime.utcnow())
    db.session.add(p)
    db.session.commit()
    return p

def apply_cycle_update_from_provisional(individual_obj: Dict[str, Any], new_prov: Dict[str, Any], prev_prov: Optional[Dict[str, Any]]):
    try:
        new_score = float(new_prov.get("score", 0.0))
    except Exception:
        new_score = 0.0
    try:
        prev_score = float(prev_prov.get("score", 0.0)) if prev_prov else 0.0
    except Exception:
        prev_score = 0.0
    conf = provisional_confidence(new_score, prev_score)
    input_count = individual_obj.get("input_count", 0)
    if input_count < individual_obj.get("MIN_STRONG_UPDATE_DAYS", 90):
        base_alpha = 0.0
    else:
        base_alpha = 0.30
    alpha = min(0.5, base_alpha + 0.2 * conf)
    try:
        last_high = datetime.strptime(individual_obj.get("last_high_prob_date", datetime.utcnow().strftime("%Y-%m-%d")), "%Y-%m-%d")
    except Exception:
        last_high = datetime.utcnow()
    cycle = float(individual_obj.get("cycle_days", 28.0))
    obs_date = _parse_ymd(new_prov.get("start_date"))
    if obs_date is None:
        return
    predicted_center = last_high + timedelta(days=cycle)
    shift = (obs_date - predicted_center.date()).days if hasattr(predicted_center, "date") else (obs_date - predicted_center).days
    new_cycle = (1 - alpha) * cycle + alpha * (cycle + shift)
    new_cycle = max(20.0, min(40.0, new_cycle))
    individual_obj["cycle_days"] = float(new_cycle)
    if conf > 0.6:
        individual_obj["last_high_prob_date"] = obs_date.strftime("%Y-%m-%d")
    new_prov["confidence"] = conf

def finalize_provisionals(individual_id: int, history_agg: Optional[Dict[str, Any]] = None):
    provs: List[ProvisionalPeriod] = ProvisionalPeriod.query.filter_by(individual_id=individual_id).order_by(ProvisionalPeriod.start_date.asc()).all()
    if not provs:
        return
    changed = False
    today = datetime.utcnow().date()
    for p in provs:
        if p.status != "active":
            continue
        if p.end_date < today:
            if history_agg and isinstance(history_agg, dict):
                score_new = 0.0
                for i in range(0, 5):
                    d = (p.end_date - timedelta(days=i)).strftime("%Y-%m-%d")
                    score_new += float(history_agg.get(d, {}).get("final_prob", 0.0))
                p.score = float(score_new)
            prev = None
            candidates = [q for q in provs if q.prov_id != p.prov_id]
            prev_parsed = []
            for q in candidates:
                if q.start_date and (p.start_date - timedelta(days=PROVISIONAL_COMPARISON_DAYS)) <= q.start_date < p.start_date:
                    prev_parsed.append((q.start_date, q))
            if prev_parsed:
                prev = sorted(prev_parsed, key=lambda x: x[0], reverse=True)[0][1]
            if prev is None:
                p.status = "finalized"
                changed = True
            else:
                if prev.score is None:
                    continue
                try:
                    if p.score is not None and p.score > (prev.score or 0.0):
                        prev.status = "discarded"
                        p.status = "finalized"
                        changed = True
                    else:
                        p.status = "discarded"
                        changed = True
                except Exception:
                    p.status = "finalized"
                    changed = True
    if changed:
        db.session.commit()
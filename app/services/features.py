import math
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

try:
    import ruptures as rpt
except Exception:
    rpt = None

try:
    from hmmlearn import hmm
except Exception:
    hmm = None

from .aggregation import aggregate_history_by_date

LABEL_THRESHOLD = 0.6
EPS = 1e-6

def extract_features_from_history(history: List[Dict[str, Any]], window_days: int = 21) -> Tuple[np.ndarray, List[datetime.date]]:
    agg = aggregate_history_by_date(history)
    dates = sorted(agg.keys())
    X = []
    dates_parsed = []
    for d in dates:
        v = agg[d]
        feat = [
            float(v.get("toilet", 0.0) or 0.0),
            float(v.get("toilet_time_mean", 0.0) or 0.0),
            float(v.get("toilet_duration_mean", 0.0) or 0.0),
            float(v.get("pain", 0.0) or 0.0),
            float(v.get("headache", 0.0) or 0.0),
            float(v.get("tone", 0.0) or 0.0),
            float(v.get("gym", 0.0) or 0.0),
            float(v.get("absent", 0.0) or 0.0),
            float(v.get("meds_count", 0) or 0.0),
            float(v.get("raw_score", 0.0) or 0.0),
            float(v.get("final_prob", 0.0) or 0.0),
            float(v.get("cough", 0.0) or 0.0)
        ]
        X.append(feat)
        try:
            dates_parsed.append(datetime.strptime(d, "%Y-%m-%d").date())
        except Exception:
            pass
    if not X:
        return np.zeros((0, 12)), []
    X = np.array(X, dtype=float)
    means = X.mean(axis=0)
    stds = X.std(axis=0) + 1e-6
    Xn = (X - means) / stds
    return Xn, dates_parsed

def detect_change_points(history: List[Dict[str, Any]], model: str = "rbf", pen: int = 3) -> List[datetime.date]:
    X, dates = extract_features_from_history(history)
    if X.shape[0] == 0 or rpt is None:
        return []
    try:
        algo = rpt.Pelt(model=model).fit(X)
        bkps = algo.predict(pen=pen)
    except Exception:
        return []
    change_indices = [b - 1 for b in bkps if b - 1 < X.shape[0]]
    candidates = [dates[i] for i in change_indices if 0 <= i < len(dates)]
    return candidates

def train_hmm_on_history(history: List[Dict[str, Any]], n_states: int = 4) -> Optional[Dict[str, Any]]:
    X, dates = extract_features_from_history(history)
    if X.shape[0] == 0 or hmm is None:
        return None
    try:
        model = hmm.GaussianHMM(n_components=n_states, covariance_type="diag", n_iter=200)
        model.fit(X)
        states = model.predict(X)
        state_counts = {}
        for s in states:
            state_counts[s] = state_counts.get(s, 0) + 1
        sorted_states = sorted(state_counts.items(), key=lambda x: x[1], reverse=True)
        top_states = [s for s, _ in sorted_states[:2]]
        candidates = []
        for i, st in enumerate(states):
            if st in top_states:
                candidates.append(dates[i])
        return {"model": model, "states": states, "dates": dates, "candidates": candidates}
    except Exception:
        return None

def generate_pseudo_labels_from_hmm_and_cp(history: List[Dict[str, Any]]) -> Tuple[List[int], List[float]]:
    X, dates = extract_features_from_history(history)
    if X.shape[0] == 0:
        return [], []
    candidates_cp = detect_change_points(history)
    hmm_res = train_hmm_on_history(history)
    labels = np.zeros(len(dates), dtype=int)
    confidences = np.zeros(len(dates), dtype=float)
    date_to_idx = {d: i for i, d in enumerate(dates)}
    for c in candidates_cp:
        idx = date_to_idx.get(c)
        if idx is not None:
            labels[idx] = 1
            confidences[idx] = max(confidences[idx], 0.6)
    if hmm_res:
        for c in hmm_res.get("candidates", []):
            idx = date_to_idx.get(c)
            if idx is not None:
                labels[idx] = 1
                confidences[idx] = max(confidences[idx], 0.5)
    agg = aggregate_history_by_date(history)
    for i, d in enumerate(dates):
        p = agg.get(d.strftime("%Y-%m-%d"), {}).get("final_prob", 0.0)
        try:
            p = float(p)
        except Exception:
            p = 0.0
        if p >= LABEL_THRESHOLD:
            labels[i] = 1
            confidences[i] = max(confidences[i], min(0.9, p))
    return labels.tolist(), confidences.tolist()
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict

def _parse_date(s: str) -> Optional[datetime.date]:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

def aggregate_history_by_date(history: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in history or []:
        d = e.get("date")
        if not d:
            continue
        grouped[d].append(e)
    for d, entries in grouped.items():
        gym_vals = [float(e.get("gym", 0) or 0.0) for e in entries]
        absent_vals = [float(e.get("absent", 0) or 0.0) for e in entries]
        pain_vals = [float(e.get("pain", 0) or 0.0) for e in entries]
        headache_vals = [float(e.get("headache", 0) or 0.0) for e in entries]
        tone_vals = []
        for e in entries:
            tp = e.get("tone_pressure")
            if tp is None:
                tp = e.get("tone")
            try:
                tone_vals.append(float(tp or 0.0))
            except Exception:
                tone_vals.append(0.0)
        toilet_counts = []
        toilet_times = []
        toilet_durations = []
        coughs = []
        meds = []
        raw_scores = []
        final_probs = []
        for e in entries:
            t = e.get("toilet")
            if t is not None:
                try:
                    toilet_counts.append(float(t))
                except Exception:
                    pass
            tt = e.get("toilet_time_mean")
            if tt is not None:
                try:
                    toilet_times.append(float(tt))
                except Exception:
                    pass
            td = e.get("toilet_duration_mean")
            if td is not None:
                try:
                    toilet_durations.append(float(td))
                except Exception:
                    pass
            c = e.get("cough")
            if c is not None:
                try:
                    coughs.append(float(c))
                except Exception:
                    pass
            m = e.get("meds") or []
            if isinstance(m, list):
                meds.extend(m)
            rs = e.get("raw_score")
            if rs is not None:
                try:
                    raw_scores.append(float(rs))
                except Exception:
                    pass
            fp = e.get("final_prob")
            if fp is not None:
                try:
                    final_probs.append(float(fp))
                except Exception:
                    pass
        def _mean(xs: List[float]) -> float:
            return float(sum(xs) / len(xs)) if xs else 0.0
        def _sum(xs: List[float]) -> float:
            return float(sum(xs)) if xs else 0.0
        out[d] = {
            "date": d,
            "gym": _mean(gym_vals),
            "absent": _mean(absent_vals),
            "pain": _mean(pain_vals),
            "headache": _mean(headache_vals),
            "tone": _mean(tone_vals),
            "toilet": _sum(toilet_counts),
            "toilet_time_mean": _mean(toilet_times),
            "toilet_duration_mean": _mean(toilet_durations),
            "toilet_times": toilet_times,
            "toilet_duration_list": toilet_durations,
            "cough": _sum(coughs),
            "meds": meds,
            "meds_count": len(meds),
            "raw_score": _mean(raw_scores),
            "final_prob": _mean(final_probs)
        }
    return out

def cluster_time_entries(entries: List[Dict[str, Any]], window_minutes: int = 60) -> List[List[Dict[str, Any]]]:
    def to_minutes(t: str) -> Optional[int]:
        try:
            parts = t.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            return h * 60 + m
        except Exception:
            return None
    times = []
    for e in entries:
        tm = e.get("time") or e.get("time_str") or e.get("time_of_day")
        mins = to_minutes(tm) if isinstance(tm, str) else None
        if mins is not None:
            times.append((mins, e))
    times.sort(key=lambda x: x[0])
    clusters: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    last = None
    for mins, e in times:
        if last is None or mins - last <= window_minutes:
            cur.append(e)
        else:
            if cur:
                clusters.append(cur)
            cur = [e]
        last = mins
    if cur:
        clusters.append(cur)
    return clusters

def collapse_entries_for_date(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    agg = {
        "date": entries[0].get("date") if entries else None,
        "toilet_count": 0,
        "toilet_times": [],
        "toilet_duration_mean": 0.0,
        "gym": 0.0,
        "absent": 0.0,
        "pain": 0.0,
        "headache": 0.0,
        "tone": 0.0,
        "raw_score": 0.0,
        "final_prob": 0.0,
        "cough": 0,
        "meds": []
    }
    if not entries:
        return agg
    gym_vals = []
    absent_vals = []
    pain_vals = []
    headache_vals = []
    tone_vals = []
    raw_scores = []
    final_probs = []
    coughs = []
    toilet_durations = []
    for e in entries:
        gym_vals.append(float(e.get("gym", 0) or 0.0))
        absent_vals.append(float(e.get("absent", 0) or 0.0))
        pain_vals.append(float(e.get("pain", 0) or 0.0))
        headache_vals.append(float(e.get("headache", 0) or 0.0))
        tp = e.get("tone_pressure")
        if tp is None:
            tp = e.get("tone")
        try:
            tone_vals.append(float(tp or 0.0))
        except Exception:
            tone_vals.append(0.0)
        raw_scores.append(float(e.get("raw_score", 0.0) or 0.0))
        final_probs.append(float(e.get("final_prob", 0.0) or 0.0))
        coughs.append(int(e.get("cough", 0) or 0))
        t = e.get("toilet_times") or e.get("toilet_time_mean")
        if isinstance(t, list):
            agg["toilet_times"].extend(t)
        elif t is not None:
            try:
                agg["toilet_times"].append(float(t))
            except Exception:
                pass
        td = e.get("toilet_duration_mean")
        if td is not None:
            try:
                toilet_durations.append(float(td))
            except Exception:
                pass
        meds = e.get("meds") or []
        if isinstance(meds, list):
            agg["meds"].extend(meds)
    def _mean(xs):
        return float(sum(xs) / len(xs)) if xs else 0.0
    agg["gym"] = _mean(gym_vals)
    agg["absent"] = _mean(absent_vals)
    agg["pain"] = _mean(pain_vals)
    agg["headache"] = _mean(headache_vals)
    agg["tone"] = _mean(tone_vals)
    agg["raw_score"] = _mean(raw_scores)
    agg["final_prob"] = _mean(final_probs)
    agg["cough"] = sum(coughs)
    agg["toilet_count"] = len(agg["toilet_times"])
    agg["toilet_duration_mean"] = _mean(toilet_durations)
    agg["meds"] = agg["meds"]
    return agg

def dedupe_meds_list(meds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not meds:
        return []
    seen = set()
    out = []
    for m in meds:
        name = (m.get("name") or "").strip().lower()
        cat = (m.get("category") or "").strip().lower()
        key = (name, cat)
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
    return out
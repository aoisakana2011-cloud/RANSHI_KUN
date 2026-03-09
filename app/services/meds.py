import os
import json
import math
from typing import List, Dict, Any, Optional
from pathlib import Path
from .io import load_meds_list_raw, save_meds_list_raw, ensure_user_meds_weights, get_user_meds_weights, save_individual, load_individual

BASE_DIR = Path(os.getcwd())
DATA_DIR = BASE_DIR / "individual_data"
MEDS_LIST_FILE = DATA_DIR / "meds_list.json"
os.makedirs(DATA_DIR, exist_ok=True)

GLOBAL_CATEGORY_WEIGHTS = {
    "生理のときにしかほぼ使わない薬": 0.9,
    "日用でも生理でも使う薬": 1.0,
    "花粉症の薬": 0.8,
    "その他の薬": 0.6,
}

WEIGHT_MIN = 0.2
WEIGHT_MAX = 1.5
LEARNING_RATE = 0.05
USAGE_WINDOW_DAYS = 90
MIN_HISTORY_FOR_UPDATE = 20

def _normalize_item(name: str, category: Optional[str] = None) -> Dict[str, Any]:
    return {"name": name, "aliases": [], "score": 0.0, "source": "seed", "category": category or ""}

def _normalize_score_value(s: Any) -> float:
    try:
        v = float(s)
    except Exception:
        return 0.0
    if 0.0 <= v <= 1.0:
        v = v * 100.0
    return max(0.0, min(100.0, v))

def load_meds_list() -> List[Dict[str, Any]]:
    try:
        if MEDS_LIST_FILE.exists():
            with open(MEDS_LIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                out: List[Dict[str, Any]] = []
                for it in data:
                    if isinstance(it, dict):
                        it.setdefault("category", it.get("category", ""))
                        it.setdefault("aliases", it.get("aliases", []))
                        it["score"] = _normalize_score_value(it.get("score", 0.0))
                        it.setdefault("source", it.get("source", "seed"))
                        out.append(it)
                return out
            if isinstance(data, dict):
                out = []
                for cat, items in data.items():
                    if not isinstance(items, list):
                        continue
                    for it in items:
                        if isinstance(it, str):
                            obj = _normalize_item(it, category=cat)
                            obj["score"] = GLOBAL_CATEGORY_WEIGHTS.get(cat, 0.5) * 100.0
                            out.append(obj)
                        elif isinstance(it, dict):
                            obj = dict(it)
                            obj.setdefault("category", cat)
                            obj.setdefault("aliases", obj.get("aliases", []))
                            obj["score"] = _normalize_score_value(obj.get("score", GLOBAL_CATEGORY_WEIGHTS.get(cat, 0.5) * 100.0))
                            obj.setdefault("source", obj.get("source", "seed"))
                            out.append(obj)
                return out
    except Exception:
        pass
    try:
        with open(MEDS_LIST_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return []

def save_meds_list(items: List[Dict[str, Any]]) -> None:
    try:
        with open(MEDS_LIST_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def seed_meds_list_from_categorized(data: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for cat, items in (data or {}).items():
        if not isinstance(items, list):
            continue
        base = GLOBAL_CATEGORY_WEIGHTS.get(cat, 0.5)
        for it in items:
            if isinstance(it, str):
                obj = _normalize_item(it, category=cat)
                obj["score"] = base * 100.0
                out.append(obj)
            elif isinstance(it, dict):
                obj = dict(it)
                obj.setdefault("category", cat)
                obj.setdefault("aliases", obj.get("aliases", []))
                obj["score"] = _normalize_score_value(obj.get("score", base * 100.0))
                obj.setdefault("source", obj.get("source", "seed"))
                out.append(obj)
    save_meds_list(out)
    return out

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

def _base_score_for_item(item: Dict[str, Any], user_weights: Optional[Dict[str, float]] = None) -> float:
    explicit = _normalize_score_value(item.get("score", 0.0))
    if explicit > 0.0:
        return explicit
    cat = (item.get("category") or "").strip()
    base = GLOBAL_CATEGORY_WEIGHTS.get(cat, 0.5)
    if user_weights and cat in user_weights:
        base = float(user_weights.get(cat, base))
    return min(100.0, base * 100.0)

def _history_boost(item_name: str, user_history: Optional[List[Dict[str, Any]]]) -> float:
    if not user_history:
        return 0.0
    cnt = 0
    name_l = item_name.lower()
    for h in user_history:
        meds = h.get("meds") or []
        for m in meds:
            if isinstance(m, str):
                if name_l in m.lower():
                    cnt += 1
            elif isinstance(m, dict):
                if name_l in (m.get("name") or "").lower():
                    cnt += 1
    return min(30.0, 10.0 * math.log1p(cnt))

def compute_med_score(item: Dict[str, Any], query: Optional[str] = None, user_history: Optional[List[Dict[str, Any]]] = None, uid: Optional[str] = None) -> float:
    user_weights = None
    if uid:
        user_weights = get_user_meds_weights(uid)
    score = _base_score_for_item(item, user_weights=user_weights)
    if query:
        q = query.strip().lower()
        name = (item.get("name") or "").lower()
        aliases = " ".join(item.get("aliases", [])).lower()
        if name.startswith(q):
            score += 40.0
        elif q in name:
            score += 20.0
        elif q in aliases:
            score += 15.0
    score += _history_boost(item.get("name", ""), user_history)
    if query and (item.get("category") or "").lower().find(query.strip().lower()) >= 0:
        score += 10.0
    return max(0.0, min(100.0, score))

def suggest_meds(query: str, limit: int = 10, user_history: Optional[List[Dict[str, Any]]] = None, uid: Optional[str] = None) -> List[Dict[str, Any]]:
    items = load_meds_list()
    scored = []
    q = (query or "").strip()
    for it in items:
        s = compute_med_score(it, query=q, user_history=user_history, uid=uid)
        scored.append((s, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored[:limit]]

def _compute_category_usage_from_history(history: List[Dict[str, Any]], window_days: int = USAGE_WINDOW_DAYS) -> Dict[str, float]:
    from datetime import datetime, timedelta
    cutoff = datetime.now().date() - timedelta(days=window_days)
    counts: Dict[str, int] = {}
    total = 0
    for h in history:
        d = h.get("date")
        try:
            from datetime import datetime as _dt
            dd = _dt.strptime(d, "%Y-%m-%d").date()
        except Exception:
            continue
        if dd < cutoff:
            continue
        meds = h.get("meds") or []
        for m in meds:
            if isinstance(m, dict):
                cat = (m.get("category") or "").strip()
            else:
                cat = ""
            counts[cat] = counts.get(cat, 0) + 1
            total += 1
    if total == 0:
        return {}
    usage = {c: counts.get(c, 0) / float(total) for c in set(list(GLOBAL_CATEGORY_WEIGHTS.keys()) + list(counts.keys()))}
    return usage

def update_category_weights_for_user(uid: str, history: List[Dict[str, Any]], lr: float = LEARNING_RATE, alpha: float = 0.6) -> bool:
    ind = load_individual(uid) or {"uid": uid}
    if "meds_category_weights" not in ind:
        ind["meds_category_weights"] = {k: float(v) for k, v in GLOBAL_CATEGORY_WEIGHTS.items()}
    usage = _compute_category_usage_from_history(history, window_days=USAGE_WINDOW_DAYS)
    if not usage:
        save_individual(uid, ind)
        return False
    if len(history) < MIN_HISTORY_FOR_UPDATE:
        lr = min(lr, 0.01)
    changed = False
    for cat in set(list(GLOBAL_CATEGORY_WEIGHTS.keys()) + list(usage.keys())):
        g = float(GLOBAL_CATEGORY_WEIGHTS.get(cat, 0.5))
        u = float(usage.get(cat, 0.0))
        target = alpha * u + (1.0 - alpha) * g
        current = float(ind["meds_category_weights"].get(cat, g))
        new_w = (1.0 - lr) * current + lr * target
        new_w = max(WEIGHT_MIN, min(WEIGHT_MAX, new_w))
        if abs(new_w - current) > 1e-6:
            ind["meds_category_weights"][cat] = float(new_w)
            changed = True
    if changed:
        save_individual(uid, ind)
    return changed
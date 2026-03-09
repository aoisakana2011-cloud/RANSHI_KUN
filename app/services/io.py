import os
import json
from pathlib import Path
from typing import Any, Dict, Optional, List

BASE_DIR = Path(os.getcwd())
DATA_DIR = BASE_DIR / "individual_data"
INDEX_FILE = DATA_DIR / "index.json"
MODELS_DIR = BASE_DIR / "models"
MEDS_LIST_FILE = DATA_DIR / "meds_list.json"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
if not INDEX_FILE.exists():
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump({"individuals": []}, f, ensure_ascii=False, indent=2)

def _safe_write(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(str(tmp), str(path))

def load_index() -> Dict[str, Any]:
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"individuals": []}

def save_index(idx: Dict[str, Any]) -> None:
    _safe_write(INDEX_FILE, idx)

def sanitize_uid(uid: str) -> str:
    return uid.replace("/", "_").replace("\\", "_").strip()

def individual_path(uid: str) -> Path:
    safe = sanitize_uid(uid)
    return DATA_DIR / f"{safe}.json"

def load_individual(uid: str) -> Optional[Dict[str, Any]]:
    p = individual_path(uid)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def save_individual(uid: str, data: Dict[str, Any]) -> None:
    p = individual_path(uid)
    _safe_write(p, data)
    idx = load_index()
    uids = list(idx.get("individuals", []))
    if uid not in uids:
        uids.append(uid)
        idx["individuals"] = uids
        save_index(idx)

def list_individual_uids() -> List[str]:
    idx = load_index()
    return list(idx.get("individuals", []))

def load_meds_list_raw() -> Any:
    if MEDS_LIST_FILE.exists():
        try:
            with open(MEDS_LIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    try:
        _safe_write(MEDS_LIST_FILE, {})
    except Exception:
        pass
    return {}

def save_meds_list_raw(obj: Any) -> None:
    _safe_write(MEDS_LIST_FILE, obj)

def model_file_for_uid(uid: str, suffix: str = "dayclf.pkl") -> str:
    safe = sanitize_uid(uid)
    return str(MODELS_DIR / f"{safe}_{suffix}")

def ensure_user_meds_weights(uid: str, default_weights: Dict[str, float]) -> Dict[str, float]:
    ind = load_individual(uid)
    if ind is None:
        ind = {"uid": uid}
    if "meds_category_weights" not in ind:
        ind["meds_category_weights"] = {k: float(v) for k, v in default_weights.items()}
        save_individual(uid, ind)
    return ind["meds_category_weights"]

def get_user_meds_weights(uid: str) -> Optional[Dict[str, float]]:
    ind = load_individual(uid)
    if not ind:
        return None
    return ind.get("meds_category_weights")

def set_user_meds_weights(uid: str, weights: Dict[str, float]) -> None:
    ind = load_individual(uid) or {"uid": uid}
    ind["meds_category_weights"] = {k: float(v) for k, v in weights.items()}
    save_individual(uid, ind)
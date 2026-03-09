import os
import json
import tempfile
from typing import Any, Optional
from datetime import datetime, date
from pathlib import Path
import hashlib

def ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)

def atomic_write_json(path: str, data: Any, encoding: str = "utf-8") -> None:
    ensure_dir(os.path.dirname(path))
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

def safe_load_json(path: str, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def sanitize_uid(uid: str) -> str:
    return uid.replace("/", "_").replace("\\", "_").strip()

def iso_date(obj: Optional[date]) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)

def model_filename_for_uid(uid: str, model_type: str = "dayclf", ext: str = "pkl") -> str:
    safe = sanitize_uid(uid)
    name = f"{safe}_{model_type}.{ext}"
    return name

def hash_string(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def ensure_models_dir(base: Optional[str] = None) -> str:
    base_dir = base or os.getcwd()
    models_dir = os.path.join(base_dir, "models")
    ensure_dir(models_dir)
    return models_dir
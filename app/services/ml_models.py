import os
import json
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional
import joblib
from .ml_advanced import extract_features_from_history, generate_pseudo_labels_from_hmm_and_cp

try:
    from lightgbm import LGBMClassifier
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

try:
    from sklearn.ensemble import RandomForestClassifier
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from sklearn.semi_supervised import SelfTrainingClassifier
    SELF_TRAINING_AVAILABLE = True
except ImportError:
    SELF_TRAINING_AVAILABLE = False

def get_models_dir():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    models_dir = os.path.join(base_dir, "models")
    os.makedirs(models_dir, exist_ok=True)
    return models_dir

def sanitize_uid(uid):
    return uid.replace("/", "_").replace("\\", "_").strip()

def train_self_training_classifier(uid, udata, force_retrain=False):
    history = udata.get("history", [])
    Xn, dates = extract_features_from_history(history)
    if Xn.shape[0] == 0:
        return None
    
    labels, confs = generate_pseudo_labels_from_hmm_and_cp(history)
    labels = np.array(labels, dtype=int)
    if labels.sum() < 3:
        return None
    
    sample_weight = np.array(confs) + 0.1
    
    if LIGHTGBM_AVAILABLE:
        base = LGBMClassifier(n_estimators=200, learning_rate=0.05)
    elif SKLEARN_AVAILABLE:
        base = RandomForestClassifier(n_estimators=200)
    else:
        return None
        
    if SELF_TRAINING_AVAILABLE:
        try:
            st = SelfTrainingClassifier(base, threshold=0.9, verbose=False)
            st.fit(Xn, labels)
            model = st
        except Exception:
            try:
                model = base.fit(Xn, labels, sample_weight=sample_weight)
            except Exception:
                model = None
    else:
        try:
            model = base.fit(Xn, labels, sample_weight=sample_weight)
        except Exception:
            model = None
            
    if model is not None:
        models_dir = get_models_dir()
        model_path = os.path.join(models_dir, f"{sanitize_uid(uid)}_dayclf.pkl")
        try:
            joblib.dump(model, model_path)
            udata.setdefault("models", {})["day_classifier"] = model_path
            return model
        except Exception:
            pass
    return None

def load_personal_classifier(uid, udata):
    model_path = udata.get("models", {}).get("day_classifier")
    if model_path and os.path.exists(model_path):
        try:
            return joblib.load(model_path)
        except Exception:
            pass
    return None

def schedule_and_train_models_for_uid(uid, udata):
    train_self_training_classifier(uid, udata)
    # 他のモデルもここで追加可能

def fused_prediction_with_models(uid, last_high, cycle_days, input_count, udata):
    from .ml_advanced import compute_prediction_distribution
    pred = compute_prediction_distribution(last_high, cycle_days, input_count)
    model = load_personal_classifier(uid, udata)
    if model is None:
        return pred
    # モデルを使った予測の融合ロジックをここに追加
    return pred

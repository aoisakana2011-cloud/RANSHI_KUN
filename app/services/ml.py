import os
import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime
from sklearn.metrics import log_loss
try:
    from sklearn.semi_supervised import SelfTrainingClassifier
except Exception:
    SelfTrainingClassifier = None
try:
    import joblib
except Exception:
    joblib = None

from .features import extract_features_from_history, generate_pseudo_labels_from_hmm_and_cp
from . import io as svc_io
from .meds import update_category_weights_for_user

MODELS_DIR = os.path.join(os.getcwd(), "models")
os.makedirs(MODELS_DIR, exist_ok=True)

def train_self_training_classifier_for_uid(uid: str, force_retrain: bool = False):
    ind = svc_io.load_individual(uid)
    if ind is None:
        return None
    history = ind.get("history", []) or []
    Xn, dates = extract_features_from_history(history)
    if Xn.shape[0] == 0:
        return None
    labels, confs = generate_pseudo_labels_from_hmm_and_cp(history)
    labels = np.array(labels, dtype=int)
    if labels.sum() < 3:
        return None
    sample_weight = np.array(confs) + 0.1
    try:
        from lightgbm import LGBMClassifier
        base = LGBMClassifier(n_estimators=200, learning_rate=0.05)
    except Exception:
        from sklearn.ensemble import RandomForestClassifier
        base = RandomForestClassifier(n_estimators=200)
    model = None
    if SelfTrainingClassifier is not None:
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
    if model is not None and joblib:
        fname = svc_io.model_file_for_uid(uid, suffix="dayclf.pkl")
        try:
            joblib.dump(model, fname)
            ind.setdefault("models", {})["day_classifier"] = fname
            svc_io.save_individual(uid, ind)
        except Exception:
            pass
    return model

def optimize_params_for_uid(uid: str) -> Optional[Dict[str, Any]]:
    ind = svc_io.load_individual(uid)
    if ind is None:
        return None
    history = ind.get("history", []) or []
    if len(history) < 10:
        return None
    Xn, dates = extract_features_from_history(history)
    labels, _ = generate_pseudo_labels_from_hmm_and_cp(history)
    labels = np.array(labels)
    if Xn.shape[0] == 0:
        return None
    feat_indices = [6, 7, 3, 4, 5]
    if Xn.shape[1] <= max(feat_indices):
        return None
    score_feats = Xn[:, feat_indices]
    coughs = Xn[:, 11] if Xn.shape[1] > 11 else np.zeros(score_feats.shape[0])
    p = ind.get("params", {})
    w = ind.get("weights", {})
    initial_params = np.array([
        float(w.get("gym", -3.0)), float(w.get("absent", 1.5)), float(w.get("pain", 1.6)),
        float(w.get("headache", 1.0)), float(w.get("tone", 0.6)),
        float(p.get("cough_max_multiplier", 1.2)), float(p.get("cough_min_multiplier", 0.2)),
        float(p.get("group1_target_prob", 0.99)), float(p.get("group2_target_prob", 0.60)),
        float(p.get("group3_multiplier", 0.5)), float(p.get("group4_add", 0.1)),
        float(p.get("score_shift", 4.0))
    ])
    bounds = [(-5.0, 0.0), (0.01, 5.0), (0.01, 5.0), (0.01, 5.0), (0.01, 5.0),
              (0.1, 2.0), (0.01, 1.0), (0.5, 1.0), (0.3, 1.0), (0.1, 1.0), (0.0, 1.0),
              (0.0, 10.0)]

    def loss(params):
        w_arr = np.array(params[:5])
        cough_max, cough_min = params[5], params[6]
        score_shift = params[-1]
        scores = np.dot(score_feats, w_arr)
        cough_mult = cough_max - (cough_max - cough_min) * (coughs / 4.0)
        scores = scores * cough_mult
        scores = scores + 1.0
        probs = 1.0 / (1.0 + np.exp(-(scores - score_shift)))
        try:
            return float(log_loss(labels, probs))
        except Exception:
            return float("inf")
    try:
        from scipy.optimize import minimize
        res = minimize(loss, initial_params, method="L-BFGS-B", bounds=bounds)
        if res.success:
            new_params = res.x
            ind["weights"] = {"gym": float(new_params[0]), "absent": float(new_params[1]), "pain": float(new_params[2]), "headache": float(new_params[3]), "tone": float(new_params[4])}
            ind["params"] = {
                "cough_max_multiplier": float(new_params[5]),
                "cough_min_multiplier": float(new_params[6]),
                "group1_target_prob": float(new_params[7]),
                "group2_target_prob": float(new_params[8]),
                "group3_multiplier": float(new_params[9]),
                "group4_add": float(new_params[10]),
                "score_shift": float(new_params[11])
            }
            svc_io.save_individual(uid, ind)
            try:
                update_category_weights_for_user(uid, history)
            except Exception:
                pass
            return ind
    except Exception:
        return None

def load_personal_classifier_for_uid(uid: str):
    ind = svc_io.load_individual(uid)
    if ind is None:
        return None
    path = ind.get("models", {}).get("day_classifier")
    if path and os.path.exists(path) and joblib:
        try:
            return joblib.load(path)
        except Exception:
            pass
    return None

def schedule_and_train_models_for_uid(uid: str):
    train_self_training_classifier_for_uid(uid)
    optimize_params_for_uid(uid)
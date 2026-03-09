import json
from pathlib import Path
from datetime import datetime, timedelta
import pytest

from app.services.io import save_individual, load_individual, load_meds_list_raw, save_meds_list_raw
from app.services.aggregation import aggregate_history_by_date, collapse_entries_for_date
from app.services.meds import load_meds_list, seed_meds_list_from_categorized, suggest_meds, compute_med_score
from app.services.features import extract_features_from_history, generate_pseudo_labels_from_hmm_and_cp

def make_sample_history():
    base = datetime(2023, 1, 1)
    hist = []
    for i in range(20):
        d = (base + timedelta(days=i)).strftime("%Y-%m-%d")
        hist.append({
            "date": d,
            "gym": 1 if i % 3 == 0 else 0,
            "absent": 0,
            "pain": 2 if i % 7 == 0 else 0,
            "headache": 0,
            "tone_pressure": 0.1,
            "toilet": 1,
            "toilet_time_mean": 7.0,
            "toilet_duration_mean": 2,
            "raw_score": 0.1,
            "final_prob": 0.9 if i % 10 == 0 else 0.0,
            "cough": 0,
            "meds": [{"name": "ロキソニン"}] if i % 5 == 0 else []
        })
    return hist

def test_io_save_and_load(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    uid = "user_test"
    ind = {"uid": uid, "history": []}
    save_individual(uid, ind)
    loaded = load_individual(uid)
    assert loaded is not None
    assert loaded.get("uid") == uid

def test_aggregation_and_collapse():
    hist = make_sample_history()
    agg = aggregate_history_by_date(hist)
    assert isinstance(agg, dict)
    assert len(agg) >= 1
    # collapse entries for a single date
    entries = [h for h in hist if h["date"].endswith("01")]
    collapsed = collapse_entries_for_date(entries)
    assert isinstance(collapsed, dict)
    assert "toilet_count" in collapsed

def test_meds_seed_and_suggest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    categorized = {
        "生理のときにしかほぼ使わない薬": ["ロキソニン", "イブ"],
        "その他の薬": ["バファリン"]
    }
    out = seed_meds_list_from_categorized(categorized)
    assert isinstance(out, list)
    items = load_meds_list()
    assert any("ロキソニン" in it.get("name", "") for it in items)
    res = suggest_meds("ロキ", limit=5, user_history=[])
    assert isinstance(res, list)
    assert len(res) >= 1
    score = compute_med_score(items[0], query="ロキ", user_history=[])
    assert isinstance(score, float)

def test_features_and_pseudo_labels():
    hist = make_sample_history()
    X, dates = extract_features_from_history(hist)
    assert X.shape[0] == len(dates)
    labels, confs = generate_pseudo_labels_from_hmm_and_cp(hist)
    assert isinstance(labels, list)
    assert isinstance(confs, list)
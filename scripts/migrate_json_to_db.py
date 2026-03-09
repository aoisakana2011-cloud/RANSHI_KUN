#!/usr/bin/env python3
"""
scripts/migrate_json_to_db.py

既存 JSON ファイル (individual_data/*.json) を DB に移行するスクリプト。

使い方:
  python scripts/migrate_json_to_db.py --path ./individual_data --dry-run
  python scripts/migrate_json_to_db.py --path ./individual_data

注意:
  - 実行前に DB のバックアップを推奨します。
  - マイグレーションは idempotent を目指していますが、必ずステージングで検証してください。
"""

import os
import json
import argparse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("FLASK_CONFIG", "app.config.ProductionConfig")

from app import create_app
from app.extensions import db
from app.models import User, Individual, HistoryEntry

def load_json_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

def migrate_one_file(session_user, filepath, dry_run=False):
    data = load_json_file(filepath)
    uid = data.get("uid") or Path(filepath).stem
    existing = Individual.query.filter_by(uid=uid).first()
    if existing:
        action = "update"
    else:
        action = "create"

    if dry_run:
        print(f"[DRY] {action.upper()} individual uid={uid}")
    else:
        if not existing:
            ind = Individual(
                uid=uid,
                user_id=session_user.id,
                cycle_days=float(data.get("cycle_days", 28.0)),
                toilet_avg=float(data.get("toilet_avg", 7.0)),
                toilet_duration_avg=float(data.get("toilet_duration_avg", 0.0)),
                input_count=int(data.get("input_count", 0)),
                last_saved=datetime.fromisoformat(data.get("last_saved")) if data.get("last_saved") else datetime.utcnow(),
                weights=data.get("weights") or {},
                params=data.get("params") or {},
                models=data.get("models") or {}
            )
            db.session.add(ind)
            db.session.flush()
            print(f"Created Individual uid={uid} id={ind.id}")
        else:
            ind = existing
            ind.cycle_days = float(data.get("cycle_days", ind.cycle_days or 28.0))
            ind.toilet_avg = float(data.get("toilet_avg", ind.toilet_avg or 7.0))
            ind.toilet_duration_avg = float(data.get("toilet_duration_avg", ind.toilet_duration_avg or 0.0))
            ind.input_count = int(data.get("input_count", ind.input_count or 0))
            ind.last_saved = datetime.fromisoformat(data.get("last_saved")) if data.get("last_saved") else ind.last_saved
            ind.weights = data.get("weights") or ind.weights or {}
            ind.params = data.get("params") or ind.params or {}
            ind.models = data.get("models") or ind.models or {}
            db.session.add(ind)
            db.session.flush()
            print(f"Updated Individual uid={uid} id={ind.id}")

        # migrate history
        history = data.get("history", []) or []
        migrated = 0
        for h in history:
            date_str = h.get("date")
            if not date_str:
                continue
            d = parse_date(date_str)
            if d is None:
                continue
            # check duplicate: same individual_id and date
            exists = HistoryEntry.query.filter_by(individual_id=ind.id, date=d).first()
            if exists:
                # update existing entry fields
                exists.gym = float(h.get("gym", exists.gym or 0.0))
                exists.absent = float(h.get("absent", exists.absent or 0.0))
                exists.pain = float(h.get("pain", exists.pain or 0.0))
                exists.headache = float(h.get("headache", exists.headache or 0.0))
                exists.tone_pressure = float(h.get("tone_pressure", exists.tone_pressure or 0.0))
                exists.toilet = float(h.get("toilet", exists.toilet or 0.0))
                exists.toilet_time_mean = float(h.get("toilet_time_mean", exists.toilet_time_mean or 0.0))
                exists.toilet_duration_mean = float(h.get("toilet_duration_mean", exists.toilet_duration_mean or 0.0))
                exists.raw_score = float(h.get("raw_score", exists.raw_score or 0.0))
                exists.final_prob = float(h.get("final_prob", exists.final_prob or 0.0))
                exists.cough = float(h.get("cough", exists.cough or 0.0))
                exists.toilet_times = h.get("toilet_times") or exists.toilet_times or []
                exists.meds = h.get("meds") or exists.meds or []
                exists.notes = h.get("notes") or exists.notes
                db.session.add(exists)
            else:
                he = HistoryEntry(
                    individual_id=ind.id,
                    date=d,
                    gym=float(h.get("gym", 0.0)),
                    absent=float(h.get("absent", 0.0)),
                    pain=float(h.get("pain", 0.0)),
                    headache=float(h.get("headache", 0.0)),
                    tone_pressure=float(h.get("tone_pressure", 0.0)),
                    toilet=float(h.get("toilet", 0.0)),
                    toilet_time_mean=float(h.get("toilet_time_mean", 0.0)),
                    toilet_duration_mean=float(h.get("toilet_duration_mean", 0.0)),
                    raw_score=float(h.get("raw_score", 0.0)),
                    final_prob=float(h.get("final_prob", 0.0)),
                    cough=float(h.get("cough", 0.0)),
                    toilet_times=h.get("toilet_times") or [],
                    meds=h.get("meds") or [],
                    notes=h.get("notes")
                )
                db.session.add(he)
                migrated += 1
        if migrated:
            print(f"  Migrated {migrated} history entries for uid={uid}")
        db.session.commit()

def main():
    parser = argparse.ArgumentParser(description="Migrate individual_data JSON files into DB")
    parser.add_argument("--path", "-p", default=str(ROOT / "individual_data"), help="path to individual_data directory")
    parser.add_argument("--dry-run", action="store_true", help="do not write to DB, just show actions")
    parser.add_argument("--user", default="admin", help="owner username to assign created individuals")
    args = parser.parse_args()

    app = create_app(os.environ.get("FLASK_CONFIG", "app.config.ProductionConfig"))
    with app.app_context():
        user = User.query.filter_by(username=args.user).first()
        if not user:
            print(f"User '{args.user}' not found. Creating a local owner user.")
            user = User(username=args.user, email=None)
            user.set_password("changeme")
            db.session.add(user)
            db.session.commit()
            print(f"Created user id={user.id} username={user.username}")

        data_dir = Path(args.path)
        if not data_dir.exists():
            print(f"Path not found: {data_dir}")
            return

        files = list(data_dir.glob("*.json"))
        if not files:
            print("No JSON files found to migrate.")
            return

        for f in files:
            try:
                migrate_one_file(user, f, dry_run=args.dry_run)
            except Exception as e:
                print(f"Error migrating {f}: {e}")

if __name__ == "__main__":
    main()
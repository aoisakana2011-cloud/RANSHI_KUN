#!/usr/bin/env python3
"""
scripts/seed_meds_list.py

meds_list.json を初期化 / シードするスクリプト。

使い方:
  python scripts/seed_meds_list.py --out ./individual_data/meds_list.json
  python scripts/seed_meds_list.py --seed seed.json --out ./individual_data/meds_list.json
"""

import os
import json
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "individual_data" / "meds_list.json"

SAMPLE_SEED = [
    {"name": "アセトアミノフェン", "aliases": ["解熱鎮痛剤"], "score": 1.0, "source": "seed"},
    {"name": "イブプロフェン", "aliases": ["NSAID"], "score": 0.9, "source": "seed"},
    {"name": "ロキソプロフェン", "aliases": [], "score": 0.8, "source": "seed"}
]

def load_seed(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_out(items, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(items)} items to {out_path}")

def main():
    parser = argparse.ArgumentParser(description="Seed meds_list.json")
    parser.add_argument("--seed", "-s", help="path to seed JSON (array of med objects)")
    parser.add_argument("--out", "-o", default=str(DEFAULT_OUT), help="output meds_list.json path")
    parser.add_argument("--merge", action="store_true", help="merge with existing file instead of overwrite")
    args = parser.parse_args()

    out_path = Path(args.out)
    if args.seed:
        seed_path = Path(args.seed)
        if not seed_path.exists():
            print(f"Seed file not found: {seed_path}")
            return
        items = load_seed(seed_path)
        if not isinstance(items, list):
            print("Seed file must contain a JSON array.")
            return
    else:
        items = SAMPLE_SEED

    if args.merge and out_path.exists():
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []
        names = { (i.get("name") or "").strip().lower() for i in existing }
        for it in items:
            if (it.get("name") or "").strip().lower() not in names:
                existing.append(it)
        write_out(existing, out_path)
    else:
        write_out(items, out_path)

if __name__ == "__main__":
    main()
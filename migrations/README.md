Alembic migration directory (minimal).

Usage (example):
1. Install alembic: `pip install alembic`
2. Create alembic.ini at project root and set `script_location = migrations`
3. Initialize DB revision:
   alembic revision --autogenerate -m "initial"
4. Apply migrations:
   alembic upgrade head

This folder contains a minimal env.py that imports your Flask app factory.
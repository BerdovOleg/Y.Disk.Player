# 005 — FastAPI skeleton + SQLite + UI shell

## Context
MVP B needs a runnable monorepo: API, catalog DB, and a static player shell.

## Decision
Python FastAPI app under `app/`, SQLite WAL schema for users/albums/tracks/favorites/history/import_jobs, Vanilla JS UI in `static/`. Serve static from FastAPI. Use `.env.example` for config keys without inventing secrets.

## Changes
- `app/main.py`, `app/config.py`, `app/db.py` (WAL schema)
- `requirements.txt`, `.env.example`
- `static/index.html`, `static/css/app.css` shell with nav views
- Empty data dir with `.gitkeep`

## Worked
`init_db()` creates schema; app imports cleanly under Python 3.14 venv.

## Failed / blocked
Plan asked for Python 3.11; machine has 3.14 only — used 3.14.

## Next
Yandex OAuth + Fernet tokens + session cookie (006).

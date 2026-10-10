# Hackathon backend (neutral core + swappable idea module)

FastAPI (Python). The core knows nothing about any one idea. PrepCrew lives in `app/modules/prepcrew/`.

## Run (Windows PowerShell)
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    copy .env.example .env        # then fill in .env; never commit it
    python init_db.py             # creates tables (safe to re-run)
    python -m uvicorn app.main:app --reload
Open http://127.0.0.1:8000/docs. Run tests with `python -m pytest -q`.

## Layout
    app/core/ai.py       generate_text / generate_json (provider-swappable, JSON validation + 1 retry)
    app/core/voice.py    speak / mint_token (provider-swappable)
    app/core/memory.py   remember / recall (memory, postgres, backboard TODO)
    app/core/jobs.py     fan_out: run tasks in parallel with timeouts and partial results
    app/core/store.py    generic records + events (Postgres, or in-memory with no database)
    app/core/routes.py   /api/health, /api/records, /api/events, /api/ai
    app/modules/<idea>/  everything specific to one idea
    sql/schema.sql       core tables; sql/<idea>.sql for module tables

## Switching ideas
1. Copy `app/modules/prepcrew` to `app/modules/<newidea>`; keep `register(app, templates)`.
2. Replace its routes, templates (`templates/<newidea>/`), and data.
3. Set `ENABLED_MODULES=<newidea>` in `.env`.
4. Store data with `core.store` (no new tables needed), or add `sql/<newidea>.sql`.
Nothing in `app/core` changes.

## Providers
`LLM_PROVIDER` and `VOICE_PROVIDER` default to `fake`, which works with no keys (good for tests and a demo fallback).
Gemini, ElevenLabs, and Backboard are stubs: implement them in `core/ai.py`, `core/voice.py`, `core/memory.py`.
Set `APP_API_KEY` before deploying so strangers can't spend your AI credits through `/api/ai/*`.

# PrepCrew backend

FastAPI (Python 3.11+). JSON API only: the React frontend owns every page. See `docs/FRONTEND_CONTRACT.md`.
Shapes follow `../contracts/` (api.md, ws_messages.md, JSON schemas).

## Run (Windows PowerShell, from this folder)
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    copy .env.example .env        # then fill in .env; never put real values in .env.example
    python init_db.py             # creates tables (safe to re-run)
    python -m uvicorn app.main:app --reload
Open http://127.0.0.1:8000/docs. Tests: `python -m pytest -q` (they never touch your database or AI keys).

## URL namespaces
    /api/*     HTTP JSON
    /ws/*      WebSockets (/ws/voice/{session_id}, /ws/board/{session_id})
    /docs      API docs, /openapi.json for generated frontend types
Nothing else. A test fails if a route is added outside these.

## Layout
    app/core/ai.py         generate_text / generate_json (fake | gemini), JSON validation + 1 retry
    app/core/voice.py      speak / mint_token (fake | elevenlabs stub)
    app/core/memory.py     remember / recall (memory | postgres | backboard TODO)
    app/core/jobs.py       fan_out: parallel tasks with timeouts, concurrency limit, partial results
    app/core/store.py      generic records + time-series events (Postgres, or in-memory with no database)
    app/core/bus.py        in-process pub/sub with replay; app/core/sse.py turns it into Server-Sent Events
    app/core/routes.py     /api/health (every other route is in the prepcrew module)
    app/modules/prepcrew/  routes.py (HTTP), ws.py (WebSockets), service.py (logic), schemas.py (shapes),
                           evaluators.py (grading pipeline), simulator.py (circuit readings), topic_graph.py
      data/scenarios/      one <scenario_id>.json per circuit (contracts/netlist.schema.json)
      data/rubrics/        one rubric per file; only status "reviewed" is used (contracts/rubric.schema.json)
      data/topics.json     skill graph {skill_id: {title, prerequisites}}
    sql/schema.sql         core tables; sql/prepcrew.sql module tables

## Database check
`python scripts/tiger_smoke.py` builds every table in a throwaway schema on the real database, runs the whole
flow against it with fake AI and voice, and drops the schema. It never touches your real tables.

## Removed on purpose
No HTML pages or static files (React owns the UI). No open `/api/records`, `/api/events` or `/api/ai` endpoints:
they let anyone read a session's answers or spend the AI key. The store they wrapped is still used internally.

## Not built yet
See `../CONTEXT.md`. In this lane: the evaluator model call (Anthropic provider in core/ai.py), writing scores and
probes to the Timescale hypertables, and second-session memory (core/memory.py is ready, nothing calls it yet).

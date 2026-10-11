# PrepCrew backend

FastAPI (Python 3.11+). JSON API only: the React frontend owns every page. See `docs/FRONTEND_CONTRACT.md`.
Shapes follow `../contracts/` (api.md, ws_messages.md, JSON schemas).

## Run (Windows PowerShell, from this folder)
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    copy .env.example .env        # then fill in .env; never put real values in .env.example
    python init_db.py             # creates tables in DATABASE_SCHEMA (safe to re-run)
    python show_tables.py         # lists them with row counts
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
    app/core/memory.py     remember / recall / forget (memory | postgres | backboard)
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

## Deploy schema
Set `DATABASE_SCHEMA=prepcrew_app` in `.env`. `init_db.py` creates that schema and builds every table in it, and the
app reads and writes only there (search_path is `"prepcrew_app", public`; TimescaleDB's functions stay in public).
Old tables in `public` from the first skeleton (users, sessions, turns, topics, lessons, evaluations) are not used
and are left untouched. Empty `DATABASE_SCHEMA` means `public`.

## Deletion guarantees
`DELETE /api/sessions/{id}` waits for an answer, probe or grading write already in progress, then removes everything;
anything that finishes later is dropped. Backboard memories that cannot be deleted right away (Backboard down) are
kept as `memory_forget_pending` pointers and retried on the next delete or memory save. `tests/test_deletion.py`.

## Database check
`python scripts/tiger_smoke.py` builds every table in a throwaway schema on the real database, runs the whole
flow against it with fake AI and voice, and drops the schema. It never touches your real tables.

## Tiger Data time-series
`sql/timeseries.sql` (from `contracts/db.sql`) adds two hypertables and a continuous aggregate. Every circuit probe is
also written to `probe_events`, every graded criterion to `answer_scores` (score 0..1), and `GET /api/mastery` reads the
`mastery_daily` continuous aggregate (real-time, so new scores show at once; `needs_review` rows never count).
`DELETE /api/sessions/{id}` deletes the session's rows from both and refreshes the aggregate. Writes are best effort:
without a database or before `init_db.py` has created the tables, the app logs one warning and carries on.
`scripts/tiger_smoke.py` checks all of this on the real database in a throwaway schema.

## Removed on purpose
No HTML pages or static files (React owns the UI). No open `/api/records`, `/api/events` or `/api/ai` endpoints:
they let anyone read a session's answers or spend the AI key. The store they wrapped is still used internally.

## Not built yet
See `../CONTEXT.md`. In this lane: the evaluator model call (Anthropic provider in core/ai.py) and writing scores
and probes to the Timescale hypertables.

## Memory across sessions (Backboard)
Set `MEMORY_BACKEND=backboard` and `BACKBOARD_API_KEY` in `.env`. When grading finishes, the debrief's gaps (with the
candidate's own quoted words) and strengths are saved, one Backboard assistant per user. The next `POST /api/plans`
for that user returns them as `memories` (most relevant to the new posting first), and the session response repeats
them as `recalled`. `DELETE /api/sessions/{id}` deletes that session's memories in Backboard too. Any Backboard error
falls back to the Postgres `memories` table, so memory never breaks a session.
Check the real API: `python scripts/backboard_check.py` (uses throwaway assistants and deletes them).

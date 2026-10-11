updated: 2026-10-11T07:19:05Z
branch: main
doing: Pi and hardware engine implementation; first fixing one Windows timing-test flake after upstream merge
next: Pi, hardware circuit integration, remaining catalog engines, accounts/history/privacy; STAR is handed off
blocked_on: human grading calibration and physical-device/audio field testing remain pending
touching: backend/app/v2 (except behavioral adapter), backend/migrations, backend/scripts, backend/tests/test_stt.py and dedicated new engine tests, frontend/src (except STAR files and circuitSymbols), frontend/e2e/session.spec.ts, docs/IMPLEMENTATION_ROADMAP.md
handed_off: Behavioral STAR drill; reserved for Joshua's teammate, see STAR_HANDOFF.md

## Implemented and pushed

Latest feature commit: `df324f1` (board/device reliability); `1b56bc2` adds implicit memory. Earlier slices are on main.

- Canonical FastAPI `/api/v2` and Vite/React/TypeScript UI; root `prototype.html` is the visual reference.
- Tiger v2.3 migrations through `008_device_resume`, seed catalog, three hypertables and two continuous aggregates. Legacy public-schema tables are preserved.
- Intake text/PDF/public GitHub README sources, exact extracted excerpts, confirmation and source attachments.
- Durable Gemini plan/review jobs, ranked catalog, prerequisites and versioned publication; generated rate-limiter requirements. Other catalog engines are still pending.
- Persisted generic session steps, transcript/event replay by seq, pause/resume/hints; Gemini interviewer and ElevenLabs streaming STT/TTS with interruption controls.
- Inline/paired board PNG critique, validated stroke targets, local geometry, separate annotations, pause review, actual QR, private-token reconnect, journal/replay, Undo/Clear and stale-review rejection. Exact demo board uses labelled recorded critique.
- Parallel evaluators, deterministic evidence checks plus independent model review, per-skill assessment, gap lesson and changed retest.
- Backboard ranks locally verified gaps for implicit openers. Durable sync/erasure outbox and evidence-derived follow-up settings; no memory UI. Live authentication verified, live CRUD result not captured and not counted as passed.
- Last completed verification: 365 backend tests, fresh Tiger migration, synthetic/mock queue and memory-race acceptance, seven isolated browser journeys. Human grading quality is not established by these fixtures.

## Run locally (PowerShell, from repo root)

Docker is not required. Use the existing root `.env`; backend `.env` is fallback and process environment has highest precedence. Never commit keys or put them in `VITE_*` variables. `/api/v2` requires a Postgres/Timescale database; the old in-memory legacy path is not a substitute.

Initial setup if needed: `python -m venv .venv`, then `.\.venv\Scripts\python -m pip install -r backend/requirements.txt`, then `cd frontend` and `npm ci`.

Apply migrations from the root (including any subsequently pulled revisions):

```powershell
$env:PYTHONPATH = 'backend'
.\.venv\Scripts\python -m alembic -c backend/alembic.ini upgrade head
```

Terminal 1, root:

```powershell
$env:PYTHONPATH = 'backend'
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173`; API docs are `http://127.0.0.1:8000/docs`. Vite proxies `/api` and `/ws`. Restart the backend after code/env changes. `DEMO_MODE=false` uses configured live providers; `true` uses explicit recorded fixtures, and custom board vision requires live mode.

At the last process check, the refreshed backend was listening on 8000 and Vite on 5173. Docker is not running. Browser acceptance starts temporary servers on 18000/15173, then stops them.

Checks: `.\.venv\Scripts\python -m pytest backend/tests -q`; in frontend, `npm test` and `npm run build`. Install browser once with `npx playwright install chromium`. From root, set `PYTHONPATH=backend` and run `.\.venv\Scripts\python backend/scripts/e2e.py`. It uses synthetic fixtures, disables paid providers, creates/drops its own uniquely named Tiger schema, and requires CREATE SCHEMA permission. Do not run ordinary demo fixtures against real user records.

## Reserved feature handoff

I am relinquishing the **Behavioral STAR drill** (`comm.star`) to Joshua's teammate. See [STAR_HANDOFF.md](STAR_HANDOFF.md) for behavior, file ownership and integration contracts. It uses the already implemented generic session/event/grading interfaces and does not depend on my remaining whiteboard, Pi, circuit, account or deployment slices.

Reserved: `backend/app/v2/behavioral.py`, `backend/app/v2/behavioral_models.py`, `frontend/src/components/StarGuide.tsx`, `frontend/src/components/StarGuide.test.tsx`, `contracts/behavioral/`, `backend/tests/test_v2_behavioral.py`, `frontend/e2e/behavioral.spec.ts`, `docs/BEHAVIORAL_STAR.md`. I keep central session/router/job/plan integration files and will wire the completed adapter; coordinate those small edits rather than changing them concurrently.

The earlier deployment/CI handoff is superseded. Deployment/CI remains in my queue; no containerization slice is being assigned to this teammate.

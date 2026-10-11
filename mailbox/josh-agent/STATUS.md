updated: 2026-10-11T10:45:25Z
branch: main
doing: implementing quota-triggered Kokoro/Parakeet browser WebGPU speech fallback
next: profile/preferences, export/deletion; hardware circuit integration and remaining engines; deployment; STAR is handed off
blocked_on: ElevenLabs live speech-to-text returned quota_exceeded; human grading and physical-device/audio checks remain pending
touching: backend/app/main.py; backend/app/v2/{realtime,voice,local_speech,routes}.py; backend/tests/test_v2_{realtime,voice,local_speech,auth}.py; frontend/src/lib/{useVoiceConversation,voiceProtocol,localSpeech,localSpeech.worker,localUtterance} and tests; frontend/src/pages/Session.tsx; frontend/src/api/{types,schemas}.ts; frontend/openapi.json; frontend/{vite.config.ts,package.json,package-lock.json}; frontend/e2e/local-{speech,voice}.spec.ts; docs/LOCAL_SPEECH.md
handed_off: Behavioral STAR drill; reserved for Joshua's teammate, see STAR_HANDOFF.md

## Implemented and pushed

Latest feature commits: `b55f311` (accounts/history), `ca263e3` (checked Pi lessons/retests), `f7ef60f` (runnable Pi lab); `df324f1` adds board/device reliability and `1b56bc2` adds implicit memory. Earlier slices are on main.

- Canonical FastAPI `/api/v2` and Vite/React/TypeScript UI; root `prototype.html` is the visual reference.
- Tiger v2.3 migrations through `010_accounts`, seed catalog, three hypertables and two continuous aggregates. Legacy public-schema tables are preserved.
- Intake text/PDF/public GitHub README sources, exact extracted excerpts, confirmation and source attachments.
- Durable Gemini plan/review jobs, ranked catalog, prerequisites and versioned publication; generated rate-limiter requirements. Pi is now runnable; the other catalog engines are still pending.
- Persisted generic session steps, transcript/event replay by seq, pause/resume/hints; Gemini interviewer and ElevenLabs streaming STT/TTS with interruption controls.
- Inline/paired board PNG critique, validated stroke targets, local geometry, separate annotations, pause review, actual QR, private-token reconnect, journal/replay, Undo/Clear and stale-review rejection. Exact demo board uses labelled recorded critique.
- Parallel evaluators, deterministic evidence checks plus independent model review, per-skill assessment, gap lesson and changed retest.
- Backboard ranks locally verified gaps for implicit openers. Durable sync/erasure outbox and evidence-derived follow-up settings; no memory UI. Live authentication verified, live CRUD result not captured and not counted as passed.
- Pi: five-stage deterministic Linux fault engine, saved terminal/editor/browser/power actions, reference validation, private state, exact tool evidence and progression gates. Commands, hardware and timings are simulated; see docs/PI_LAB.md. Existing-plan migration 009 ran on Tiger and made eight proposed Pi tracks ready. Checked lessons and executable retests now run through the durable queue. Two authored variants change the port, directory traversal, log lifecycle and power-history interpretation while retaining the rubric. Full 3D interaction remains pending.
- Accounts/history: sign-in/register, hashed server sessions, all v2 HTTP/WS ownership checks, legacy API disabled by default, cursor history and second-device plan recovery. Old workspaces remain preserved; operator-only credential binding is documented in docs/ACCOUNTS.md. Email recovery/verification and full export/erasure remain pending.
- Last completed verification: 623 backend tests; 90 frontend tests and build; authenticated account browser journey plus Pi and intake/whiteboard/fleet compatibility passed. All eight older isolated browser journeys passed across earlier suite/focused runs. Fresh Tiger migration, synthetic/mock queue and memory-race acceptance passed; synthetic/recorded Pi learning acceptance verifies rejected-review nonpublication, audited retry, changed engine, same rubric, source citations and idempotent retest start. Human grading quality is not established by these fixtures.

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

Open `http://127.0.0.1:5173` and register/sign in; API docs are `http://127.0.0.1:8000/docs`. Vite proxies `/api` and `/ws`. Restart the backend after code/env changes. `DEMO_MODE=false` uses configured live providers; `true` uses explicit recorded fixtures, and custom board vision requires live mode.

At the last process check, the refreshed backend (PID 2600, migration 010, authentication enabled) was listening on 8000 and Vite on 5173. Docker is not running. Browser acceptance starts temporary servers on 18000/15173, then stops them.

Checks: `.\.venv\Scripts\python -m pytest backend/tests -q`; in frontend, `npm test` and `npm run build`. Install browser once with `npx playwright install chromium`. From root, set `PYTHONPATH=backend` and run `.\.venv\Scripts\python backend/scripts/e2e.py`. It uses synthetic fixtures, disables paid providers, creates/drops its own uniquely named Tiger schema, and requires CREATE SCHEMA permission. Do not run ordinary demo fixtures against real user records.

## Reserved feature handoff

I am relinquishing the **Behavioral STAR drill** (`comm.star`) to Joshua's teammate. See [STAR_HANDOFF.md](STAR_HANDOFF.md) for behavior, file ownership and integration contracts. It uses the already implemented generic session/event/grading interfaces and does not depend on my remaining whiteboard, Pi, circuit, account or deployment slices.

Reserved: `backend/app/v2/behavioral.py`, `backend/app/v2/behavioral_models.py`, `frontend/src/components/StarGuide.tsx`, `frontend/src/components/StarGuide.test.tsx`, `contracts/behavioral/`, `backend/tests/test_v2_behavioral.py`, `frontend/e2e/behavioral.spec.ts`, `docs/BEHAVIORAL_STAR.md`. I keep central session/router/job/plan integration files and will wire the completed adapter; coordinate those small edits rather than changing them concurrently.

The earlier deployment/CI handoff is superseded. Deployment/CI remains in my queue; no containerization slice is being assigned to this teammate.

## Voice startup diagnosis

A controlled live connection using the current root env authenticated, then the provider returned quota_exceeded when synthetic silent audio began. No candidate speech was sent. Two bounded diagnostic sessions were opened; actual billed cost is not available. Do not retry live calls in a loop. Available ElevenLabs quota is required for streaming STT. Text/lab behavior remains available.

Commit b42cd32 maps quota/auth/terms/rate/input failures to safe actionable messages and persists the error in generation_jobs; no raw provider bodies are forwarded. All 51 targeted voice/realtime tests passed, including quota failures before/after handshake, cleanup and audit assertions. These are mocked regression tests, not evidence that live quota has been restored. Local API now runs PID 16744 on 8000.


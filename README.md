# PrepCrew

An interview gym for hardware and infrastructure roles. Investigate a simulated fault, get feedback tied to your own work, learn the exact gap, then prove it on a changed retest.

Built for CodeRED: Orion at the University of Houston.

Live site: _(fill in after deploy)_

## Why

Building a project and explaining why it breaks are different skills. A student can ship a working embedded or server project and still freeze when an interviewer asks, "Why is this failing?" Most prep tools hand them another list of questions. PrepCrew watches how they investigate, finds where the reasoning stalls, teaches that gap, and tests it again under changed conditions.

AI runs on physical infrastructure: power, servers, chips and the systems that connect them. More CS and computer engineering students are aiming at roles near that stack. PrepCrew trains the foundational reasoning those interviews screen for, starting with Linux server diagnosis and system design.

## What it does

1. **Set a goal.** You give a goal, a question you struggled with, and optional sources (pasted text, a PDF, or a public GitHub README). Sources are excerpted exactly and need your confirmation before use.
2. **Get a plan.** A recoverable background job builds a prioritized plan from the supported drills.
3. **Investigate.** You debug a simulated Raspberry Pi server through five stages with Dana, the AI interviewer, using a terminal, an editor, a browser view and power checks. Your commands, edits and explanations are saved as separate evidence. You can also whiteboard a system design and request an annotated critique.
4. **Review.** Evaluators grade the session in parallel. Every claim must cite something you actually did or said. Local checks verify each quote against the exact session event, and an independent model review decides whether the quote supports the judgment. Nothing publishes if either check fails.
5. **Learn.** A verified gap opens a short lesson, labeled AI generated.
6. **Retest.** You get a changed task (a different port, directory, log setup or power history) that tests the same skill under the same rubric, so repeating the same command is not enough.
7. **Remember.** Your next session can open from the gap your last one revealed.

Currently playable drills: `infra.pi_site` (the Pi fault lab) and `sw.sysdesign` (system design with a whiteboard). Other catalog entries are planned and are not runnable yet.

## How it differs from existing tools

Big Interview offers adaptive interview practice. Voltage Learning offers hardware interview preparation. Jobright is a job search copilot with AI mock interviews. LeetCode covers coding practice. We reviewed their public pages and did not find a tool that combines tool-action evidence from a playable lab, quote-checked feedback, a gap-specific lesson, and a changed retest that carries into the next session. This is a finding about the pages we reviewed, not a claim that no one does it.

## Simulation and other limits

- The Pi lab is **simulated**. Its commands, hardware and timings are produced by our own deterministic engine. It is not a real shell, not real hardware, and not a copy of a real interview. The 3D view is our own teaching aid.
- AI feedback is practice guidance. Rubrics have not been calibrated by human engineers yet (`contracts/grading-review.json` sets `human_calibrated: false`). Exact quote checks prevent fabricated evidence, but a correct quote can still support a wrong interpretation.
- We have no tester outcome data, so we make no claim about learning gains.
- Cloud speech depends on provider quota. Typing always works. A local browser speech fallback (Kokoro and Parakeet) is under verification and is not part of the committed build unless noted in the release.
- Demo and fixture data are **synthetic**. Recorded model responses are labeled as recorded.
- A circuit-level hardware debugging engine, behavioral (STAR) practice, general drill generation, networking and GPU labs are roadmap items.
- Password recovery, full data export and deletion, and a production deployment are unfinished.

## How it works

```
Browser (React + TypeScript)   workspace for talking, drawing and investigating
        |  HTTP /api/v2  and  WebSocket /ws
FastAPI + asyncio              auth, sessions, jobs, evaluators, lab engine
        |
Tiger Data (Postgres + TimescaleDB)   ordered session events, assessments, metrics
```

| Component | Job | Tool |
|---|---|---|
| Frontend | Workspace, Pi lab and 3D view, whiteboard, history | React, TypeScript, Vite, Three.js |
| Session engine | Persisted steps, ordered events, pause and resume | FastAPI, asyncio |
| Pi lab | Five-stage deterministic fault engine with reference-tested variants | Python |
| Interviewer | Dana's replies and plan generation through audited jobs | Gemini |
| Speech | Streaming speech to text and text to speech | ElevenLabs |
| Whiteboard | Stroke board with validated targets, vision critique of a snapshot | Gemini |
| Evaluators | Parallel grading, exact evidence checks, independent semantic review | Gemini |
| Learning loop | Gap, lesson, changed retest with the same rubric | Python, Gemini |
| Memory | Ranks and syncs remembered gaps; the app recalls only locally verified text | Backboard |
| Data | Events, assessments, hypertables and continuous aggregates (mastery, latency) | Tiger Data |
| Accounts | Argon2id password hashing, hashed server sessions, ownership checks on HTTP and WebSocket | Python |

The live loop uses a fast Gemini model because turn latency decides whether the conversation feels natural. Grading runs in the background on a model configured separately, because quality matters more than speed there.

## Run it locally

You need Python 3.11 or newer, Node.js, and a Postgres or TimescaleDB database (Tiger Data works). The `/api/v2` app requires the database. Docker is not required.

Put your keys in a `.env` file in the repo root (a `backend/.env` is used as a fallback). Start from `backend/.env.example`. Never commit `.env`, and never put keys in `VITE_*` variables.

| Variable | Used for |
|---|---|
| `GEMINI_API_KEY` | Plans, interviewer, evaluators, whiteboard critique, lessons |
| `ELEVENLABS_API_KEY` | Streaming speech |
| `ELEVENLABS_VOICE_ID` | A voice your plan can use |
| `BACKBOARD_API_KEY` | Memory |
| `DATABASE_URL` | Tiger Data or Postgres connection string |
| `DEMO_MODE` | `false` uses live providers, `true` uses explicit recorded fixtures |

`backend/.env.example` lists the rest.

**First-time setup** (from the repo root, PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
```

**Apply migrations** (also after pulling new revisions):

```powershell
$env:PYTHONPATH = 'backend'
.\.venv\Scripts\python -m alembic -c backend/alembic.ini upgrade head
```

**Run the backend** (terminal 1, repo root):

```powershell
$env:PYTHONPATH = 'backend'
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Run the frontend** (terminal 2):

```powershell
cd frontend
npm run dev
```

Open http://127.0.0.1:5173 and register an account. API docs are at http://127.0.0.1:8000/docs. Vite proxies `/api` and `/ws` to the backend. Restart the backend after code or env changes.

**Tests:**

```powershell
.\.venv\Scripts\python -m pytest backend/tests -q     # backend
cd frontend; npm test; npm run build                  # frontend
```

Browser acceptance uses synthetic fixtures, disables paid providers, and creates and drops its own uniquely named schema, so it needs CREATE SCHEMA permission. Install the browser once with `npx playwright install chromium`, then run `backend/scripts/e2e.py` with `PYTHONPATH=backend`. Do not run demo fixtures against real user records. See `frontend/README.md` for the full list of commands.

## API

Interactive docs are served at `/docs`. Main groups:

| Route group | Purpose |
|---|---|
| `/api/v2/auth/*` | Register, sign in, sign out |
| `/api/v2/sources*` | Intake sources, exact excerpts, confirmation |
| `/api/v2/sessions/{sid}/lab` | Pi lab actions |
| `/api/v2/sessions/{sid}/board` | Whiteboard strokes and critique requests |
| `/api/v2/sessions/{sid}/lesson/jobs` | Lesson generation for a verified gap |
| `/api/v2/retests` | Start a changed retest |
| `/ws/v2/pair/{code}` | Optional second-device pairing |

The legacy API from the first prototype is disabled by default. Shapes in `contracts/` describe earlier targets, and the current v2 models and routes are authoritative.

## Measured results

Every number here comes from logs or a real run. Blanks mean we have not measured it yet. Early latency smoke tests from the legacy path (one laptop, tiny samples, not benchmarks) are recorded with their caveats in `spikes/RESULTS.md`.

| Metric | Value |
|---|---|
| Tester sessions run (with consent) | |
| Mastery change, first test to retest | |
| Evaluator agreement with hand grading | |
| Speech end to first reply audio, v2 | |
| Evaluator fleet completion time | |
| Model cost per completed session | |

## Privacy and honesty

- Lessons are generated by a model and labeled "AI generated" in the app. Seeded demo data is labeled "synthetic".
- Sessions need consent. Account ownership is checked on every v2 HTTP and WebSocket request.
- When you use speech, audio goes to ElevenLabs. Text and board images go to Gemini. Memory text goes to Backboard. With local speech, raw audio stays on the device but recognized text is still sent online.
- Full user-facing export and deletion, and remote deletion verification, are not finished yet. Use synthetic data until they are.
- The rubric and one lesson were reviewed by: _(name, role, and what they said, filled in after the review)_

## Roadmap

Calibrate rubrics with practicing engineers, then run a consented pilot with a campus engineering organization and measure retest gains on held-out tasks. After that: constrained drill generation validated before launch, a circuit and embedded engine, behavioral interview practice, networking labs, and cohort reporting. Each ships only once it has evidence rules we trust. The full plan is in [`docs/IMPLEMENTATION_ROADMAP.md`](docs/IMPLEMENTATION_ROADMAP.md).

## More documentation

- [`frontend/README.md`](frontend/README.md): frontend commands and verified behavior
- [`docs/PI_LAB.md`](docs/PI_LAB.md): the simulated Pi lab
- [`docs/ACCOUNTS.md`](docs/ACCOUNTS.md): accounts and ownership
- [`docs/GRADING_REVIEW.md`](docs/GRADING_REVIEW.md): evidence and grading review
- [`docs/WHITEBOARD_DEVICES.md`](docs/WHITEBOARD_DEVICES.md): whiteboard and device pairing
- [`spikes/RESULTS.md`](spikes/RESULTS.md): early smoke measurements

## Team

Hugo Santos, Joshua Eworo, Shamah Amichoh, Trey De'De

## License

_(to be decided)_

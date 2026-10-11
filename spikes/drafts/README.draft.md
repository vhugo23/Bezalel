<!--
REVIEW NOTES (delete this block before this replaces README.md). Checked against the repo at 4f2b84d.
- "docker compose up --build" and "cp .env.example .env": there is no Dockerfile, no compose file and no root .env.example
  (find found only backend/.env.example and frontend/.env.example). backend/app/config.py reads the ROOT .env.
- API table: every legacy route is under /api (routes.py, prefix="/api"); the lesson route is GET /api/lessons/{skill_id}
  (routes.py get_lesson). The React app uses /api/v2 (v2/routes.py). The sockets are /ws/voice/{id} and /ws/board/{id}.
- docs/architecture/ does not exist; docs/ holds GRADING_REVIEW.md and IMPLEMENTATION_ROADMAP.md only.
- Old "What it does" items 3 to 7: no scenario file ships (data/scenarios has only .gitkeep, so a probe returns 404),
  there is no DC solver or schematic view, no draw-it-first for hardware, no debugging-process rubric in either app
  (data/rubrics has only .gitkeep, so the legacy grader has nothing to grade with), topics.json is {} so there are no
  skills or lessons in the legacy app, and the hardware tracks in the React app are seeded as "proposed".
- The 3D breadboard note is gone: there is no breadboard view in frontend/, backend/ or prototype.html.
- Numbers in "Measured results" are copied from spikes/RESULTS.md and CONTEXT.md (origin/context-update, 8558d63) with their
  line numbers. Nothing else. The React app's claims come from frontend/README.md and docs/IMPLEMENTATION_ROADMAP.md and
  were not re-run.
- Items marked FILL IN need a person.
-->

# PrepCrew

A voice interview coach for hardware and embedded engineering students.

Built for CodeRED: Orion at the University of Houston.

Live site: FILL IN (nothing is deployed yet, so there is no site)

## Status in one paragraph

This repository holds two apps that do not share an interviewer. The **voice interviewer** (`backend/app/modules/prepcrew/`, test page `spikes/voice_check/`) is the hardware and embedded interview: a project interview from a posting and a resume, a patience meter, and a debrief. The **React app** (`frontend/`, `backend/app/v2/`) is the full product shell: plan, skill circles, voice and whiteboard sessions, evidence-checked grading, a lesson and a retest. Its one runnable session is a software design question (a rate limiter), and its hardware tracks are preview cards that cannot be started. The circuit debugging part of the idea, a schematic with a planted fault that the candidate probes, is **not built** in either app. Nothing is deployed.

## What works today

### The voice interviewer (hardware and embedded)

1. You paste a job posting and a resume (`POST /api/plans`). A model picks one resume project, writes 4 to 6 short spoken questions and reads up to 12 skills from the posting, each marked required or preferred. If the model fails you get generic questions and `degraded: true`.
2. You talk to it over `/ws/voice/{session_id}`, typing or with push-to-talk (speech to text by ElevenLabs). Replies come from Gemini, are written to sound spoken (short, no praise, no stock phrases) and are read back by ElevenLabs, with barge-in.
3. A hidden patience meter watches for two things: you say you have not used a skill the posting requires, or you ignore the question. A required gap moves it a lot, a preferred gap a little. In a strict session two required gaps (or three ignored questions) end the interview with a closing line. A gap only counts if the quote the model reports is word for word in your answer; a model failure or timeout counts for nothing. The weights are hand-picked and not validated.
4. A debrief lists the gaps worst first with your own words, the strengths, and up to two links per gap from a 24-entry resource library. No model writes it. No person has reviewed the links.
5. After you end the session, notes from the debrief are saved as memory for a next plan. The interviewer does not use them yet.

### The React app

Per `frontend/README.md` (not re-run for this README): intake, a persisted plan with four skill circles and track cards, database-backed sessions driven by stored scenario steps, a voice conversation with an interviewer called Dana, a whiteboard with a model critique of the drawing, grading with exact quote and event checks plus a second model's review, a lesson written from a verified gap, and a changed retest. An iPad pairing route exists and was designed for local testing only.

## What is not built

- **Circuit walkthrough.** No scenario file ships, so there is no circuit to probe: a probe request returns 404. There is no DC solver and no schematic view. After the project part, the voice interviewer answers with a placeholder line ("Okay. What would you check next?").
- **Draw a schematic first.** The whiteboard exists in the React app for the software design session only.
- **Grading the debugging process** (supply first, ground checked, isolate before swapping, state a hypothesis). A draft rubric exists in `contracts/examples/debug_process_rubric.json`, unreviewed. Neither app ships a reviewed hardware rubric, so the voice interviewer's `/end` step has nothing to grade with.
- **Hardware in the React app.** The hardware tracks are seeded as `proposed`. `contracts/examples/led_reversed.v2.json` is the reversed LED scenario in the React app's scenario format. It is data only and nothing loads it.
- **Skills, lessons and a mastery chart for hardware.** The voice interviewer's skill graph is empty (`topics.json` is `{}`), so there are no lessons for it. Lessons and retests exist in the React app for the software session only.
- Deployment, accounts and authentication. There is no Dockerfile, no compose file and no hosted site.

## How it differs from existing tools

We have not done a market survey. The earlier README named Big Interview, Voltage Learning and Jobright and said none grades a debugging process or links an interview gap to a lesson and a retest. We have not re-checked that, and because the debugging part is not built, this is not something we can claim to have shipped. FILL IN (the team should decide whether to keep any comparison).

## How it works

```
Browser (React app)  voice over websocket, whiteboard canvas, plan and results
Browser (test page)  spikes/voice_check, a throwaway page for the voice interviewer
FastAPI + asyncio    one process, both apps, run locally
```

| Component | Job | Status |
|---|---|---|
| Voice interviewer | Plan, spoken turns, patience meter, debrief. Gemini and ElevenLabs | Built, legacy path |
| Dana | The React app's own voice loop, whiteboard critique, step progression | Built for the software session |
| Session state | Legacy: intake, interview, walkthrough (placeholder), debrief. React app: persisted steps per scenario | Built |
| Evaluators | One call per rubric, quotes checked against what was said, a second model reviews the claim | Built for the software rubric. No hardware rubric |
| Circuit solver | Node voltages from a netlist | Not built. `simulator.py` only returns stored voltages from scenario files, and none ship |
| Curriculum | Skill graph, lessons, mastery | React app, software only |
| Memory | Weak spots carried to the next session | Voice interviewer: saved and recalled, not used by the interviewer. React app: a verified gap is stored in Postgres and read back into the next session's opening. Backboard is wired in code with a local fallback, and its use is not verified in this repo |
| Data | Postgres, with Tiger Data (TimescaleDB) hypertables for events and scores | Needed by the React app. The voice interviewer runs in memory without it |

The live loop uses a small, fast Gemini model because turn time decides whether it feels like a conversation. Grading runs after the session and can use a different model (`EVALUATOR_MODEL`).

## Measured results

Every number below is copied from `spikes/RESULTS.md` or `CONTEXT.md` (the version on branch `origin/context-update`, commit `8558d63`, which the line numbers below refer to; on `main` the same text is at lines 61 and 82). Samples are small, from one laptop on one network on Sat Oct 10, 2026. They are not benchmarks. A blank means we have not measured it.

| Metric | Value | Sample and caveat | Source |
|---|---|---|---|
| Gemini first token, `gemini-3.5-flash-lite` | 1050, 967 ms | 2 runs, one short prompt, no long prompt tested | `spikes/RESULTS.md` line 14 |
| Gemini first token, `gemini-3.8-flash` (default) | 4737, 5292, 28590 ms | 3 runs; too slow for the live loop | `spikes/RESULTS.md` line 10 |
| Interviewer reply text ready (server `turn_total`) | 964 to 1270 ms | 10 turns (2 runs of 5), made-up posting and resume, scripted answers, includes storing the answer and the reply | `spikes/RESULTS.md` lines 73 to 76 |
| Interviewer plan call | 4.5 to 5.8 s; 1.7 s in one later run | 5 runs, then 1 | `spikes/RESULTS.md` lines 109 and 142 |
| First audio from ElevenLabs, `eleven_flash_v2_5` | 1382, 640, 588 ms | 3 runs, the first was cold; the default model took 2345, 3292, 1534 ms | `spikes/RESULTS.md` lines 34 to 35 |
| Speech to text, `scribe_v2` | 1558, 991, 824 ms | one synthetic clip, same words each time; says nothing about real or noisy speech | `spikes/RESULTS.md` line 44 |
| Speech end to interviewer reply start | | Not measured end to end | `spikes/RESULTS.md` line 50, `CONTEXT.md` line 104 |
| Evaluator fleet completion time | | No figure in either source | |
| Tester sessions run (with consent) | | No count recorded | |
| Mastery change, first test to retest | | Not measured | |
| Evaluator agreement with hand grading | | Not measured. `docs/GRADING_REVIEW.md` says no accuracy figure is available | |
| Gap check agreement with the author's own labels | 17 of 20 skill checks; 14 of 14 ignored-question checks | The labels were written by the author, not independent | `spikes/RESULTS.md` lines 121 and 157 |
| Patience meter ending an interview with a live model | Meter 0.0, 0.6, 1.2 in one clean run; 0.0, 0.6, 0.95, 1.55 in one debrief run | Each ended the interview. `RESULTS.md` says the first "reproduced only once", and later runs hit busy Gemini errors, so the meter stayed at 0.0 by design | `spikes/RESULTS.md` lines 135, 137 to 139 and 189 |
| Average words per spoken reply, old persona against new | 18.5 against 11.7 | 10 replies per side, scripted answers, a generic fallback plan on one run per side. Whether it sounds human was not judged | `spikes/RESULTS.md` line 96 |
| Resource links that load from a script | 21 of 24 | 3 returned 403 to the script and loaded when read earlier. Links are unreviewed by a person | `spikes/RESULTS.md` line 185 |
| Whole loop over real sockets with every real provider | 23 of 23 checks passed | One run, one synthetic voice, on a local branch on Oct 10 | `CONTEXT.md` line 121 (`origin/context-update`) |

The reply times are also shown on screen in the test page, read from the server's own timings.

## Honesty notes

- Lessons in the React app are generated by a model, then checked by a second model call. They carry an `ai_generated` flag. As far as this repo shows, no lesson, rubric or resource link has been reviewed by a person. Review of the debug rubric and one lesson: FILL IN (name and role, and what they said, only if a review happens).
- Fixtures and recorded demo data are marked synthetic and are not real user data. The posting and resume in the test page are made up.
- A session needs a consent flag. The voice interviewer deletes a session and its data with `DELETE /api/sessions/{id}`. Deleting the React app's artifacts is not implemented (`frontend/README.md`).
- The meter's thresholds, the rubric criteria and the anchors are starting values chosen by us and not validated. A wrong "unknown" would end a real person's practice interview, and the false-end rate has not been checked with a second person's labels.
- Gemini was busy in bursts during our runs. The system then asks the planned question and counts nothing, so the meter can under-count. The meter message says when it could not check an answer (`checked: false`).

## Run it locally

You need Python 3.11 or newer. The React app also needs Node and a Postgres with TimescaleDB (Tiger Data).

### Tests (no keys, no network, no database)

```
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest -q
```

The tests use fake providers and blank the database setting themselves.

### The voice interviewer

Put your keys in a file called `.env` in the **repository root** (not in `backend/`; `backend/app/config.py` reads the root file). `backend/.env.example` lists every variable and is a good template. Never commit `.env`. Leave `DATABASE_URL` out of it for this app, which then keeps everything in memory.

| Variable | Used for |
|---|---|
| `LLM_PROVIDER` | `gemini` for the real model. The default `fake` needs no key and has no meter |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Plans, replies and the gap check. `GEMINI_MODEL` has no default |
| `VOICE_PROVIDER` | `elevenlabs` for real speech. The default is `fake` |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | Speech in and out |
| `BACKBOARD_API_KEY`, `MEMORY_BACKEND` | Optional memory |
| `DATABASE_URL` | Optional Postgres. Required by the React app |

To start the backend with in-memory storage whatever your `.env` says, run this from `backend/`:

```
.venv\Scripts\python -c "import os; os.environ['DATABASE_URL']=''; import uvicorn; uvicorn.run('app.main:app', port=8000)"
```

Then, in another terminal, serve the test page and open http://localhost:5173/ :

```
cd spikes\voice_check
python -m http.server 5173
```

`GET http://127.0.0.1:8000/api/health` shows which providers are active. A rehearsal script is in `DEMO_RUNBOOK.md` (draft).

### The React app

Follow `frontend/README.md`: install the backend requirements, run `alembic -c backend/alembic.ini upgrade head` against your Postgres, start the API from the repository root with `PYTHONPATH=backend`, then `npm ci` and `npm run dev` in `frontend/`. Only the software design track can be started.

## API

The voice interviewer, all under `/api`:

| Route | Purpose |
|---|---|
| `POST /api/plans` | Posting and resume in, plan out (project, questions, skills, `degraded`) |
| `POST /api/sessions` | Start a session (needs `consent: true`; `strict` lets the meter end it) |
| `WS /ws/voice/{session_id}` | Speech or text in; text and 16 kHz audio out; meter and state messages |
| `POST /api/sessions/{id}/turns` | Typed answer (the fallback for voice) |
| `GET /api/sessions/{id}/debrief` | Gaps with quotes, strengths and links |
| `POST /api/sessions/{id}/end` | Grade the session (nothing to grade with until a reviewed rubric exists) |
| `GET /api/sessions/{id}/events` | Grading progress over SSE |
| `GET /api/sessions/{id}/report`, `DELETE /api/sessions/{id}` | Report, and delete everything for a session |
| `POST /api/sessions/{id}/probe`, `WS /ws/board/{session_id}` | Circuit probes. Returns 404 until a scenario file exists |
| `GET /api/skills`, `GET /api/lessons/{skill_id}`, `POST /api/retests`, `GET /api/mastery`, `GET /api/metrics/{session_id}` | Empty or 404 for hardware until skills and lessons exist |
| `GET /api/health` | Active providers and whether a database is set |

The React app uses `/api/v2/...` (plans, sessions, events, turns, board, hint, pause, end, report, lesson, retests, pair) and the sockets `/ws/v2/voice/{id}`, `/ws/v2/sessions/{id}` and `/ws/v2/pair/{code}`. The generated schema is `frontend/openapi.json`.

## Known limits

- The two apps do not share an interviewer, a database layer or a session model. Hardware interviews run only in the voice interviewer.
- There is no circuit to debug, no solver and no schematic view.
- The meter needs a real model and is silent on the fake provider. When Gemini is busy it under-counts.
- Speech accuracy on real, accented or noisy speech has not been measured. Only one synthetic voice was tested.
- Rubrics, the meter and the resource library have not been reviewed by a person.
- The model routes have no authentication or rate limit, and locks are per process, so run one worker. Do not expose the API.
- No code sandbox.

## Team

FILL IN (names and what each person built)

## License

FILL IN (not decided)

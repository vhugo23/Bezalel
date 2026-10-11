# PrepCrew: context for whoever picks this up next

Written Sat Oct 10, 2026, late evening, from the working session. Read this first, then `contracts/api.md`,
`contracts/ws_messages.md` and `spikes/RESULTS.md`. The original brief (`prepcrew-opus-brief.md`, outside the repo) still
sets the rules; the short version is below.

## Current state (refreshed hourly; last 2026-10-11T07:35Z at `b0a9038`)
This section is kept current by trey-agent's hourly review. Where it disagrees with an older section below, this one is right.
The detail behind it is in `mailbox/REVIEW.md`.

**Time left:** Devpost submission is due Sun Oct 11 at noon Central (17:00Z). Hacking ends 1 PM.

**There are two apps in the repo. They are not joined yet, but the pieces to join them are now on `main`.**
- Legacy path: `backend/app/modules/prepcrew`, routes under `/api`, sockets `/ws/voice` and `/ws/board`, test page `spikes/voice_check`. The hardware and embedded voice interviewer with the patience meter, assessor, humanlike persona and debrief.
- v2 path: `backend/app/v2`, routes under `/api/v2`, the React app in `frontend/`, Alembic migrations in `backend/migrations`, schema `prepcrew` in Tiger Data. Intake sources, generated plans, voice and whiteboard session, evidence-checked grading, lessons, retests, memory, and QR pairing to a second device. Its one runnable session is still a software rate-limiter design.
- The bridge: `backend/app/modules/prepcrew/hardware_interview.py` (`start`, `answer`, `debrief`, plain JSON state, no storage) and `contracts/examples/hw_circuit_debug.two_step.v2.json` with its answer key in a separate file. josh-agent has said it will wire them into `hw.circuit_debug`. Not started.
- Humans have not yet said which app is the demo or what is cut. Trey: "the cut list and demo are coming but do all you can without it" (`mailbox/HUMAN.md`).

**Who is doing what**
| Agent | Last seen | Doing | Landed since Oct 10 evening |
|---|---|---|---|
| trey-agent | 07:29Z | Paused by Trey. Only this hourly review continues. | #11 lane 1 entry point, LED scenario, submission drafts in `spikes/drafts/`. #12 backup model for busy Gemini (`GEMINI_BACKUP_MODEL`, off by default). #13 two-step hardware scenario. All three are on `main` through #13. Open: #14 circuit symbol stamps (`frontend/src/lib/circuitSymbols.ts`, a library, not wired into any screen) |
| josh-agent | 07:22Z | Pi and hardware engine work; says circuit integration is next | React app, v2 backend, migrations, roadmap. Scenario-driven sessions (`0daf815`). `.env` fix (`c891d23`). Recoverable lessons (`859fc57`). Intake sources (`ec4679c`). Generated plans (`6c2521e`). Memory (`1b56bc2`). Whiteboard review safety and QR pairing with reconnect (`df324f1`, notes in `docs/WHITEBOARD_DEVICES.md`) |
| shamah-agent | no mailbox activity | Unknown | Nothing since Shamah's own commits on Oct 10 (Tiger time-series, Backboard memory, backend cleanup) |
| hugo-agent | no mailbox activity | Unknown | Nothing |

josh-agent pushes code straight to `main` on Joshua's instruction. Its Behavioral STAR drill is handed to "Joshua's teammate" with reserved files (`mailbox/josh-agent/STAR_HANDOFF.md`); nobody has claimed it in the mailbox. The lanes table in `mailbox/README.md` is still unfilled.

**Open problems right now**
1. **`set DATABASE_URL=` and `$env:DATABASE_URL=''` do not blank the variable, they remove it, and the loader then fills it from `.env`.** `backend/app/environment.py` loads process environment, then root `.env`, then `backend/.env`. So an "in-memory" start command on a machine with a database URL in either file uses the real Tiger Data database and starts the v2 grading worker on it. To force in-memory storage, run from `backend/`: `python -c "import os; os.environ['DATABASE_URL']=''; import uvicorn; uvicorn.run('app.main:app', port=8000)"`. For tests: `python -c "import os,sys,pytest; os.environ['DATABASE_URL']=''; sys.exit(pytest.main(['-q']))"`.
2. Neither app has a hardware debug walkthrough. There is no circuit solver and no schematic view. The React app's hardware tracks are still `proposed`. `contracts/examples/led_reversed.v2.json` must not be loaded as a scenario: it puts the planted fault in the model prompts. Use `hw_circuit_debug.two_step.v2.json` with `hw_circuit_debug.answer_key.json` in `scenarios.params`.
3. iPad drawing has not been tried on a device. Pairing needs the frontend started with `npm run dev -- --host 0.0.0.0` and the laptop's LAN address typed into the pairing dialog (`docs/WHITEBOARD_DEVICES.md`). Venue wifi may block device-to-device traffic. The circuit stamps have no tool button yet, and nobody has looked at how they render.
4. Nothing is deployed and there is no Dockerfile or compose file, although `README.md` tells you to run `docker compose up`. `README.md` "What it does" items 3 to 7 are not built for hardware in either app. A corrected README and a Devpost description are drafts in `spikes/drafts/`; nobody has applied them. The video, screenshots, team names and license have no owner.
5. `docs/IMPLEMENTATION_ROADMAP.md` is an 11 phase product plan, not a plan for the hours left. josh-agent says it is not a promise for noon.
6. Running the backend tests on Windows leaves a `backend/%SystemDrive%/` folder behind (the PDF test in `test_v2_sources.py`; `v2/sources.py` starts its child process without `SYSTEMDRIVE`). Delete it, do not commit it.
7. After pulling: `pip install -r backend/requirements.txt` (`pypdf` and others were added) and `npm ci` in `frontend/` (`qrcode` was added).

**Checked at this refresh, on `main` at `b0a9038`:** backend `pytest` 526 passed (stubbed models, database forced off). Frontend `npm test` 16 passed and `npm run build` succeeded, on Node 24.20. Not run: the Playwright browser journeys, anything against Tiger Data, any live Gemini or ElevenLabs call. josh-agent's own reports of those were not repeated.

**Waiting on**
- josh-agent: wiring `hardware_interview` and the two-step scenario into `hw.circuit_debug`; a tool button for the circuit stamps once #14 is merged.
- Humans: which app is the demo; what is cut before noon; who owns the submission; an iPad test; merge or close #11, #12 (both already on `main` through #13) and #14.

## What this is
PrepCrew is a voice interview coach for hardware and embedded engineering students, built for CodeRED: Orion
(University of Houston). Hacking ends Sun Oct 11, 1 PM Central; submit on Devpost by noon. The venue locks 12 AM to 9 AM.
The loop: paste a job posting and resume, get a spoken interview that follows up on what you say, a debug walkthrough on a
schematic with a planted fault, evaluators that grade with quoted evidence, a debrief with resources, then a retest.

## Rules from the brief that still apply
1. Never invent numbers. Every latency, accuracy, score, tester count in the product, README or pitch comes from a log or a real run, or is left blank.
2. Label AI-generated lessons "AI generated" and seeded demo data "synthetic".
3. Positioning must be accurate. Never write "no one does this". The 3D breadboard is our teaching aid, not what real interviews use.
4. No keys in the repo. Keys live in `backend/.env` (gitignored). Never print them.
5. Tester sessions need a consent note and must be deletable. Store only what the dashboard needs.
6. Do not deploy or push overnight without human review. (This session pushed branches and opened PRs because the user asked each time.)
7. Prefer simple Python (FastAPI, asyncio). No agent framework. Each human must be able to explain their lane.
8. Write tests that try to break the main flow: bad model JSON, timeouts, dropped websockets.

## People and lanes
(Written Oct 10 evening. The frontend now exists and lanes have moved; see "Current state" above.)
The user is on GitHub as KTreyD. The repo is `vhugo23/Bezalel` (teammate owns it). Lane 1 voice and interviewer is what this
session built. Lane 3 backend and data (a teammate) wrote the `service.py` / routes / websocket skeleton and `sql/`.
Lane 4 frontend and deploy has not started: there is no `frontend/` folder and no Node install on this machine. `prototype.html`
on `main` is a design prototype only (it makes no API calls). Lane 2 circuit and whiteboard and lane 5 content are not in the repo yet.

## How to run it
Windows, Git Bash or PowerShell. Python 3.13 here; the code needs 3.11 or newer (`asyncio.timeout`).

    cd backend
    .venv\Scripts\python -m pip install -r requirements.txt  # needed again after 9399673
    .venv\Scripts\python -m pytest -q                      # 321 pass at b1d5939, no keys or network needed
    # backend with real providers. NOTE: "set DATABASE_URL=" removes the variable, it does not blank it; see "Current state" problem 3.
    set VOICE_PROVIDER=elevenlabs & set ELEVENLABS_MODEL=eleven_flash_v2_5 & set DATABASE_URL= & .venv\Scripts\python -m uvicorn app.main:app --port 8000
    cd spikes\voice_check & python -m http.server 5173     # test page: http://localhost:5173/  (Ctrl+F5)

`backend/.env` holds the keys and these non-secret settings: `LLM_PROVIDER=gemini`, `GEMINI_MODEL=gemini-3.5-flash-lite`,
`ELEVENLABS_VOICE_ID` set, `VOICE_PROVIDER=fake` by default (override it when starting the server, as above).
`DATABASE_URL` points at the real Tiger Data database. **Never run `init_db.py` or any script without blanking `DATABASE_URL`
unless you mean to write to it.** Tests do this automatically in `tests/conftest.py`. Every script in `spikes/` sets it blank.
To stop servers: find the listeners on ports 8000 and 5173 with PowerShell `Get-NetTCPConnection` and stop only those two.

## What is built (all in `backend/app`)
- `core/ai.py` Gemini over REST (teammate's), `generate_json` with one retry. `core/voice.py` ElevenLabs streaming text to speech (`stream`, `speak`) and speech to text (`transcribe`, `scribe_v2`, upload). The fake provider never invents a transcript.
- `modules/prepcrew/service.py` sessions, answers, probes, grading, metrics, deletion (teammate's), plus my `handle_answer` and `build_debrief`. Storage is the generic `core/store.py` records and events, in memory or Postgres.
- `interviewer.py` builds the plan (project, topics, 4 to 6 short spoken questions, skills with `required` or `preferred`) and picks each next line. Spoken-style persona with examples, five turn "shapes" (dig, clarify, challenge, react_and_move, bridge) never repeated twice in a row, variant pools for fallback questions, hand-off, closing and walkthrough placeholder. Live turns time out at 5 s and fall back to the planned question (`source: "fallback"`).
- `humanness.py` cheap checker for chatbot tells (praise, stock phrases, dashes, emojis, length, repeated openings, parroting) and a sanitizer. Live replies are counted, not regenerated.
- `assessor.py` one model call per answer, run beside the reply: does the answer admit a gap on a posting skill, and did it answer the interviewer's question at all. Anything it reports counts only if its quote appears word for word in the answer. Failure or timeout means no penalty.
- `meter.py` the patience meter. Starting values, hand-picked and NOT validated: required unknown 0.6, required partial 0.25, preferred unknown 0.15, preferred partial 0.05, ignored question 0.35 each time. Wrap-up push at 0.5, a strict session ends at 1.0. Each skill counts once. One answer adds at most 0.6, so ending takes two answers. `strict=false` never ends. Needs a real model (null on the fake provider). Applies to the project interview only.
- `debrief.py` and `resources.py`, `data/resources.json` (24 links). `GET /api/sessions/{id}/debrief`: gaps worst first with the candidate's own quotes, strengths, up to two links per gap, a template summary. No model writes it. **Every resource is `reviewed: false`** until a person reviews it.
- `retry.py` one retry on a busy provider (503, 429, 5xx). `ws.py` voice socket (text or push-to-talk audio in, text then binary 16 kHz PCM audio out, barge-in, timing, meter, state, `debrief_ready`) and board socket (teammate's).
- Main flow: plan, session (consent, `strict`), opening question, answers (typed or spoken), meter, closing line on an early end (state `debrief`, then `debrief_ready`), `POST /end` for grading, report.

## Pull requests
All of #1 to #8 are merged as of Oct 11, and none are open. The rest of this paragraph is history.
#1 and #2 are merged. #3 (real interviewer check) was merged into `main` on its own. #4 speech in, #5 humanlike interviewer, #6 patience meter and
#7 debrief were built as a stack, so **#7 contains all of them and is the one to merge** (a regular merge commit, not a squash). It was merged with the
newest `main` (teammate's prototype and schema, and #3) and was mergeable and clean when last checked. #4 shows as conflicting because #3 landed separately;
ignore it, #7 carries its changes, and close #4 to #6 after #7 merges.

## Measured so far (small samples, one laptop, not benchmarks; details and caveats in `spikes/RESULTS.md`)
- Gemini lite first token about 1.0 s in early spikes; a live turn about 1.0 to 1.4 s; `gemini-3.8-flash` was 2.7 to 28.6 s and is too slow for the live loop. The plan call took 1.7 to 5.8 s.
- ElevenLabs first audio 1382, 640, 588 ms over three runs on the flash model, the first one cold (2345, 3292, 1534 ms on the default); 616 to 852 ms in the later end-to-end runs. Speech to text 824 to 1558 ms on one synthetic clip, exact words.
- Persona change, 10 replies per side: average 18.5 words became 11.7. Whether it sounds human is for a person to judge (`spikes/_runs/blind_read.md`, `spikes/_runs/voice_ab/`, both local and gitignored).
- Meter against my own labels (not independent): 14 of 14 on ignored-question checks, 17 of 20 on skill checks. A real two-skill interview ended once as designed.
- A full spoken turn (speech to text, reply, first audio) has NOT been measured end to end.

## Known problems and risks
(Written Oct 10 evening, about the legacy path. Since then: memory for session two, the Tiger time-series tables and a frontend have been built, and grading uses Gemini, not Opus. Items 5, 6, 9 and 10 are partly out of date.)
1. **Gemini availability.** In bursts about half the calls return busy errors or time out even after the retry. The system degrades safely (planned questions, no penalty) but the meter then under-counts, and `checked: false` says so. Likely free-key rate limits, not confirmed. A backup model or a paid key would fix it.
2. The assessor sometimes misses a gap when one answer admits several. It errs toward being gentle.
3. A wrong "unknown" would end a real person's practice interview. Hand-check the false-end rate with a second person's labels before the first tester session.
4. Resource links are unreviewed. 3 of 24 refuse scripts (DigiKey, two Wikipedia pages) but loaded when read. Re-check with `spikes/check_resource_links.py`.
5. **Two storage models.** The backend runs on generic `records` and `events`. The teammate's new `sql/prepcrew.sql` (about 40 relational tables) is not used by any code. `memories` is defined in both SQL files; `init_db.py` runs `schema.sql` first, so the richer definition is silently skipped on a fresh database, and re-running against an existing database keeps old tables. Someone must decide the migration.
6. The backend has never been run against a real Postgres. Only the in-memory store is tested.
7. Deleting a session removes its events and records but the plan record (resume and posting text) is only removed if `store.delete_linked` covers it. Check before tester sessions.
8. Locks are per process, so run one uvicorn worker. The model routes have no auth or rate limit (the browser calls them, so a key would be visible). Add a rate limit at deploy.
9. Not built: the walkthrough interviewer (after the project part, replies are a placeholder), memory for session two (phase 6), skill graph and lessons (`topics.json` empty), real scenarios (`data/scenarios` is empty, only `contracts/examples/led_reversed.json`, whose 2.0 V LED drop is my assumption), the Opus evaluator provider, spoken debrief, frontend, Vultr deploy, domain, iPad whiteboard.
10. Spikes still not run, per the brief: Backboard (and whether it routes Opus), Tiger Data hypertable and continuous aggregate, Gemini reading hand-drawn schematics, Pencil canvas on iPad Safari. `contracts/db.sql` Timescale syntax is unverified.

## Integration check status
Run Sat Oct 10 evening on the local `debrief` branch (everything stacked, plus the newest `main`).
- **Whole loop over real sockets, every real provider: 23 of 23 checks pass** (`spikes/e2e_full.py`, needs the backend running). Plan from Gemini, opening question spoken, a spoken answer through speech to text, a typed answer, a second spoken answer, the meter going 0.0, 0.6, 1.2, the interview ending, the closing line then `debrief_ready`, answers refused afterwards with the socket still open, the debrief fetched from the browser's origin (CORS ok), every quote real, every link in the library, grading started, report, metrics, deletion, and a deleted session having no debrief. One run, one synthetic voice.
- Measured in that run: speech to text 849 to 890 ms, first audio 616 to 699 ms, a turn (store, model, store) 1.67 s, plan 2.8 s. Speech to text turned "the motors started" into "the motor started" and "five volt" into "five-volt" (94 percent of words matched). The summed pause a candidate hears after speaking is still not measured as one number.
- 219 unit and integration tests pass in the working venv and in a fresh venv built from `requirements.txt` (no hidden dependencies).
- Every open PR branch (#3 to #7) merges cleanly into the newest `main`. Contract examples validate against the JSON schemas. SQL foreign keys are in a valid order.
- **Not verified:** the backend against a real Postgres (only the in-memory store has ever run). `init_db.py` was deliberately not run against the real database, and no local Postgres or Docker is available here (WSL has an Ubuntu image, nothing installed in it). The browser page's JavaScript was never run by me, only by the user (voice, meter and "You:" line were confirmed working by them; the debrief panel and the new buttons have not been confirmed).
- `backend/docs/FRONTEND_CONTRACT.md` and `backend/.env.example` were refreshed to match the code.

## Suggested next steps
1. Have the user confirm the debrief panel in the browser, then merge PRs #3 to #7 in order. Get a real Postgres test (a throwaway schema in Tiger Data, or Postgres in WSL) before relying on the database.
2. Decide the storage model (generic records versus the new relational schema) and fix the duplicate `memories`.
3. Walkthrough interviewer that reacts to probe events, using a real scenario from the content owner.
4. Memory for session two, then the evaluator (Opus) provider with the evidence checker the contracts describe.
5. A person reviews the resource list and the debug rubric; run the false-end check on the meter.
6. Backup Gemini model, then the unrun spikes, then frontend integration and deploy.

## Working notes for this machine
- Git Bash mangles long inline Python heredocs that contain triple quotes. Write patch scripts to a file and run them.
- Real-API scripts in `spikes/` cost a few ElevenLabs characters and some Gemini calls, and a burst of about 25 calls in a minute got rate limited. Space calls out.
- `e2e_*.py` scripts use the Starlette TestClient (a new event loop per request); that is why they blank `DATABASE_URL`.
- The user prefers short plain explanations, honest reporting of failures, a plan shown before big builds, concise commit messages, and wants to stop and test by ear or by eye before the next phase. Commit messages and PR bodies end with the attribution lines the harness specifies.
- Tests are the spec. Several behaviors were proven by breaking the code on purpose (mutation checks) and confirming a test failed.

# PrepCrew

PrepCrew is a team-built interview practice app from CodeRED: Orion. Dana interviews you while you work through a simulated Linux troubleshooting lab or a system-design whiteboard, then gives feedback tied to saved evidence and a lesson/retest for supported gaps.

## Run one app

Requires Node.js 22.12+ and Python 3.11+. From this repository:

```sh
npm ci
npm run setup
npm start
```

Open http://127.0.0.1:8000, register, and open **Connections**. Choose your model provider and speech options, save your API key, and test the connection. The launcher builds on React/TypeScript, FastAPI and ordinary PostgreSQL but runs them as **one app at one address**. It manages a native local Postgres process automatically; Docker and separate frontend hosting are not required. Stop with Ctrl+C. After changing frontend source, run `npm run build`.

Live practice is the default. `npm start -- --demo` explicitly selects recorded fixtures and labeled autoplay without paid model calls. Recorded output does not measure your ability. Existing root `.env` cloud credentials are not used as other users' BYOB credentials.

## Live interview and BYOB

- **Models:** Gemini, OpenAI, Anthropic, and OpenAI-compatible APIs, including approved hosted endpoints and localhost models. Each account saves its own provider/model settings and encrypted API keys; keys are never returned to the browser. A compatible endpoint must support the requested structured output and images for board critique.
- **Voice:** continuous microphone capture, interruption/barge-in, reply audio, and conversation tied to the current interview step. Dana can react sparingly to relevant lab/board activity without supplying the solution. Assessment remains a separate evidence-based pipeline.
- **Speech choices:** ElevenLabs real-time transcription, OpenAI utterance transcription, or local Parakeet; ElevenLabs/OpenAI reply audio, local Kokoro, or installed browser voices. OpenAI transcription sends completed utterances rather than streaming partial captions. Mic capture remains active during replies.
- **Local speech:** Kokoro uses WebGPU and selectable female voices. Parakeet compact mode uses an FP16 encoder and INT8 decoder (mixed precision), requiring `shader-f16`; compatibility mode permits a much larger FP32 encoder. Downloads are roughly 325 MB for Kokoro and 690 MB for compact Parakeet, cached by the browser. GPU support and available memory matter. Matching ONNX runtime files are served by this app.

There is no PrepCrew usage fee; cloud providers charge your own API account. ChatGPT/Claude/Gemini consumer subscriptions are not connected through OAuth and are not substitutes for API keys. Local speech keeps audio processing on your device; the selected model still receives the interview context and board images when used. Cloud speech receives the audio/text needed for its selected operation.

## What is implemented

Two authored drills: a deterministic five-stage Linux/Pi server simulation with terminal, configuration editor, browser and power checks; and system-design interviews with an editable whiteboard and snapshot critique. Linux commands are simulated, not a real shell. Other catalog topics are previews; arbitrary generated skill tracks are not implemented.

Accounts, session ownership, ordered work events, pause/resume, history, persisted jobs and retry recovery support the practice loop. Versioned rubrics, exact evidence checks and independent model review support feedback, lessons and changed retests. Postgres stores the job queue and verified gap memory. Timescale, Backboard, Redis and separate workers are not required. Use one API worker.

## Data and hosting

Local data defaults to `.artifacts/app`; preserve the entire directory, including the database, `database.password` and `provider.key`. Losing the encryption key makes saved provider credentials unreadable. `PREPCREW_DATA_DIR` chooses another persistent directory. Stop the app before filesystem backups. Do not commit local data or secrets.

To host one service, set `PREPCREW_PUBLIC=true`, `PUBLIC_BASE_URL=https://your-host`, and a durable `PREPCREW_DATA_DIR`, then run the same launcher behind HTTPS. An external standard Postgres can be selected using `DATABASE_URL`. The optional `deploy/Dockerfile.app` packages the same single service for hosts that require an image; local use does not require it. See [operations and limits](docs/PORTFOLIO.md).

## Verification

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python -m pytest backend/tests -q
npm test
npm run build
npm run check:app
```

`check:app` starts an isolated native database and packaged app, registers an account, and tests a synthetic local compatible provider. Browser acceptance uses `backend/scripts/e2e.py`, a disposable schema and no paid AI calls; set `E2E_ADMIN_DATABASE_URL` to a local test Postgres and install Playwright Chromium first. `--auth accounts.spec.ts connections.spec.ts` includes account/provider isolation. Hardware speech smoke is opt-in with `PREPCREW_LOCAL_GPU_SMOKE=1`.

Rubrics are not calibrated against human interviewers; there are no measured hiring or learning outcomes. General generated tracks and real hardware simulation remain future work. Password recovery and complete account deletion remain unfinished. Real-device microphone/acoustic reliability needs broader field testing. Do not present recorded fixtures as real evaluations or claim personal ownership of teammates' work.

[Architecture and resume scope](docs/PORTFOLIO.md) · [Migration notes](backend/migrations/README.md) · [Pi lab](docs/PI_LAB.md) · [Grading review](docs/GRADING_REVIEW.md)

# PrepCrew React app

Vite + React + strict TypeScript. The approved root `prototype.html` supplies the visual tokens and layout in `src/prototype.css`; the application is native React, with no embedded mockup or global DOM scripting.

## Run locally (PowerShell, from the repository root)

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements.txt
.\.venv\Scripts\python -m alembic -c backend/alembic.ini upgrade head
$env:PYTHONPATH='backend'
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` and `/ws`. Keys stay in the root server `.env`. `frontend/.env.example` contains only the optional public API origin.

## What works

- Intake, persisted plan, four SVG skill circles, domain tabs, catalog previews, and the authored system-design track.
- Database-backed sessions and event log with server-assigned `seq`; websocket reconnect resumes after the last received sequence.
- Voice-first conversation with both speakers in a persistent transcript, a hands-free microphone loop, mute, interrupt, replay, optional typing, and Pointer Events whiteboard (pen, boxes, arrows), undo/clear, candidate-only PNG snapshot, structured critique, validated shape targets, separate animated annotation layer, and Dana cursor.
- Exact sample-board matching selects a cached critique. A different board requires live mode. The UI allows continuing without critique if the provider is unavailable.
- Concurrent rubric evaluations, exact citation checks plus independent model support review, rejection display, source-event dialogs, saved per-skill scores, measured latency, and a verified-gap lesson/retest loop.
- Server-minted single-use iPad pairing code and a Pencil-friendly `/pair/:code` route; strokes are saved through a websocket and relayed through the shared event log.
- Live Gemini adapter uses `google-genai` structured output. ElevenLabs adapter accepts a recorded microphone turn for STT and streams TTS through the backend. API keys never reach the client.

## Explicit limits

- Live mode is the default (`DEMO_MODE=false`). Explicitly set `DEMO_MODE=true` for recorded interview/evaluator fixtures and browser speech. Exact sample-board critique remains cached by design. Secrets are loaded from the root `.env` regardless of the server working directory; restart the API after changing them.
- Live Gemini replies, ElevenLabs TTS/STT, and the combined HTTP audio-turn ? reply-audio path passed real provider checks. The local interviewer uses `gemini-3.5-flash-lite`; Dana uses ElevenLabs Sarah (`EXAVITQu4vr4xnSDxMaL`) with `eleven_flash_v2_5`. These are server settings, not browser credentials. The current key can synthesize/transcribe but cannot list voices (`voices_read` is not required by the app).
- Voice uses an AudioWorklet to send continuous 16 kHz PCM through `/ws/v2/voice/:id` to ElevenLabs `scribe_v2_realtime`. Capture remains active during Dana's TTS playback. Provider partial transcripts appear live; only committed transcripts become candidate evidence. Provider background filtering, browser echo cancellation/noise suppression, and a conservative verbatim playback-echo check reduce false activations. This is not speaker identification: a nearby person can still be transcribed, and headsets help in a noisy room.
- Recognized speech interrupts playback and cancels pending Gemini generation. Revision checks suppress late audio/results. Muting disables the microphone track and sends silence to keep the connection alive. End voice/disconnect releases the track and audio context. Network loss deliberately stops capture and offers Restart via Start voice, rather than retaining unbounded audio for replay.
- Dana chooses `continue`, `advance`, `look`, `finish`, or `listen` in validated structured output. Step changes apply only after the current reply finishes, never after an interruption, and cannot skip steps. Drawing statements remain silent; a spoken request to look snapshots the board. Manual controls remain available. Typed answers also use the pacing decisions. Completion starts grading automatically when Dana closes the final discussion.
- A real streaming test received partial captions, interrupted an active Dana reply, and saved the subsequent committed utterance. The model-only test with `gemini-3.5-flash-lite` took 2.51 seconds; one streaming run took about 2.5 seconds from the thinking state to reply. These are observed samples, not latency guarantees. Speaker playback is streamed by a separate HTTP connection; microphone input is simultaneous. Live speech separation across different rooms/devices still needs field testing.
- Live whiteboard critique was verified on a real 20-stroke freehand board: two validated annotations, separate animated marks, and successful ElevenLabs playback. One successful `gemini-3.5-flash-lite` vision call took 3.12 seconds; earlier calls timed out, so this is not a latency guarantee. `WHITEBOARD_MODEL` selects the vision model independently. Strict schemas use Gemini's `response_json_schema` field; using the legacy schema field rejected `additionalProperties`. Full strokes and PNGs are persisted before the vision call; the request uses a compact stroke log with every target id, bounds, and sampled path. Live evaluator quality still needs dedicated acceptance tests.
- Plan selection is deterministic intake inference over the authored catalog. General plan/scenario generation, sandboxed engines, Pi 3D, and STAR remain unavailable; preview cards never imply a runnable engine.
- Scores remain empty in demo mode. Live scores use authored, versioned 0Ã¢â‚¬â€œ4 practice criteria, mapped to the appropriate skill and converted to 0Ã¢â‚¬â€œ100. Activity alone cannot establish ability; unknown skills, wrong-step citations and unsupported claims are rejected. An independent model checks entailment and score consistency after deterministic reference/quote checks. This is not a correctness proof, and human calibration remains pending.
- Grading uses persisted `grading` sessions as its queue, with PostgreSQL advisory locks, atomic publication, restart recovery and retry of failed evaluators. Partial reviews do not publish mastery, lessons or memory. The complete fleet must succeed, but unobserved criteria remain unassessed. Previous-score comparisons require supported claims from the same rubric version.
- A complete review with a verified gap can generate a saved lesson and changed conceptual retest. A second model checks the teaching and prompt before the new track becomes ready. Repeated generation/start requests reuse the saved result. The retest uses the new scenario prompt, links its parent and focus skill, and retains source claim/event references. No verified gap means no invented remedial lesson. A successful retest retires its offered card and stops its original gap appearing in openers only when the original criterion reaches the authored threshold (3/4); this threshold also needs calibration.
- Verified gap memory currently uses Postgres. Backboard and adaptive difficulty are not connected. Lesson generation is request-driven: retry after an interruption; a saved lesson survives restart. Durable execution for other generation subjects remains future work.
- Pairing was designed for local testing; physical iPad/Safari, HTTPS, and reconnect of the paired device still need testing. Main-session websocket reconnect works. A used pairing code must currently be replaced after a paired-device disconnect.
- PNGs live in ignored `.artifacts/` for local development. S3 storage, authentication/authorization, deletion of v2 artifacts, and deployment are not implemented. Keep the API on localhost until those are added.

## Checks

```powershell
# from frontend
npm run build
npm test
# From repository root; starts isolated API + Vite and cleans up its test schema:
.\.venv\Scripts\python backend/scripts/e2e.py

# from repository root
$env:PYTHONPATH='backend'
.\.venv\Scripts\python -m pytest backend/tests -q
.\.venv\Scripts\python backend/scripts/verify_v23.py
# Read-only validation of an already completed live parent/retest pair:
.\.venv\Scripts\python backend/scripts/verify_learning_loop.py PARENT_ID RETEST_ID
```

Verified: 321 backend tests and 15 frontend tests, production build, Tiger Data invariants, browser lesson generation and retest start, plus a controlled live Gemini/Tiger learning loop. Synthetic candidate utterances exercised real providers, 11 accepted claim references, gap-derived teaching, changed retest, mastery comparison, duplicate requests, partial failure/retry and interrupted-worker recovery. These fixtures are not human interview results or evidence of grading accuracy. Two standalone Playwright acceptance journeys pass against a freshly migrated disposable Tiger Data schema: intake/board/reload/grading/evidence, and ordered replay/idempotency/stale-step rejection. Run them with backend/scripts/e2e.py; live providers are disabled. Human grading calibration remains pending in docs/GRADING_REVIEW.md.

The database verifier rolls back its fixtures. It checks hypertables, continuous aggregates, evidence constraints, absence of foreign keys to hypertables, monotonic seq, and out-of-order mastery updates.

## API contract

`openapi.json` is exported from FastAPI. `npm run api:generate` creates both `src/api/types.ts` and runtime Zod validators. Do not hand-edit either generated file.

```powershell
# from repository root, after editing backend models
$env:PYTHONPATH='backend'
.\.venv\Scripts\python -c "import json; from app.main import app; from pathlib import Path; Path('frontend/openapi.json').write_text(json.dumps(app.openapi(),indent=2),encoding='utf-8')"
cd frontend
npm run api:generate
```

Checked primary references: [Vite](https://vite.dev/guide/), [Tailwind Vite integration](https://tailwindcss.com/docs/installation/using-vite), [OpenAPI TypeScript](https://openapi-ts.dev/node), [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output), [ElevenLabs STT](https://elevenlabs.io/docs/api-reference/speech-to-text/convert), [ElevenLabs streaming TTS](https://elevenlabs.io/docs/api-reference/text-to-speech/stream).

## Realtime voice protocol

The browser sends 100 ms mono PCM16 frames (16 kHz) as binary websocket messages. JSON controls are `text`, `interrupt`, `commit`, `mute`, `replay`, `playback_started`, `playback_done`, `playback_failed`, and `stop`. Server messages are runtime-validated in `voiceProtocol.ts`: `ready`, `partial`, `committed`, `reply`, `interrupt`, `state`, `look`, and `error`. Reply/interrupt messages carry a monotonically increasing connection revision. A reconnect starts a new STT audit job; saved evidence continues in the existing session event log. One active voice connection per session is enforced for the local single-worker server.

Realtime parameter reference: [ElevenLabs realtime STT](https://elevenlabs.io/docs/api-reference/speech-to-text/v-1-speech-to-text-realtime). `filter_background_audio=true` is enabled without word timestamps, which the provider documents as incompatible. Model-call retries are owned by the app so each attempt has a separate `generation_jobs` row. Interrupted attempts end as failed with a Cancelled stage (the existing database status enum has no cancelled value).

Whiteboard regression coverage includes preserving spoken answers when the model also returns `listen`, filler-led and split questions, strict JSON Schema transport, and retaining a snapshot after provider failure. Primary references: [Gemini JSON Schema](https://ai.google.dev/gemini-api/docs/structured-output), [Gemini 3.5 Flash-Lite image input](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite).

Evaluator schema compatibility: nested bounded claim/quote arrays caused live HTTP 400 responses. Only the rubric decoder schema relaxes array bounds; the original Pydantic limits still validate every response. Validation retries provide field/type corrections without echoing rejected candidate content. Other schemas, including the four-mark board limit, keep their wire bounds. See [Gemini structured-output limitations](https://ai.google.dev/gemini-api/docs/structured-output).

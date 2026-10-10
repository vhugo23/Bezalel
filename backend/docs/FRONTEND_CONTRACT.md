# Frontend <-> backend contract

Two folders, two owners. Neither edits the other's folder.

| | Backend | Frontend (React) |
|---|---|---|
| Folder | `backend/` | `frontend/` (create it at the repo root) |
| Dev server | `python -m uvicorn app.main:app --reload` -> http://127.0.0.1:8000 | `npm run dev` -> http://localhost:5173 |
| Owns | `/api/*`, `/ws/*`, the database, every API key | every page and route (`/`, `/plan`, `/session/...`), all UI |

Shapes and routes are agreed in `contracts/` at the repo root (`api.md`, `ws_messages.md`, the JSON schemas).
The running backend publishes the exact shapes at `/openapi.json` (browse them at `/docs`).

## Rules
1. **Namespaces.** Backend routes live only under `/api` (HTTP) and `/ws` (WebSockets). A test fails if a
   backend route lands anywhere else. The backend serves no pages and no `/static` (SERVE_HTML=false).
2. **One base URL.** The frontend reads it from one env var (`VITE_API_URL`) or uses the dev proxy below. Never hardcode it.
3. **No keys in the frontend.** Voice tokens come from `POST /api/sessions` (`voice_token`).
4. **Types from the schema, not by hand:**
   `npx openapi-typescript http://127.0.0.1:8000/openapi.json -o src/api/types.ts`
5. **Changing a shape:** update `contracts/` first and tell the other side. Adding fields is safe; renaming or removing breaks code.
6. **Errors** are JSON `{"detail": "message"}` with a non-200 status (400 bad input, 404 not found, 501 not built yet).
   WebSocket errors are `{"type": "error", "code", "message", "recoverable"}`.

## Dev setup (recommended: Vite proxy, no CORS involved)
```js
// frontend/vite.config.js
export default {
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/ws':  { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
}
```
Then call `fetch('/api/...')`, `new EventSource('/api/sessions/ID/events')`, `new WebSocket(\`ws://${location.host}/ws/voice/ID\`)`.

Calling the backend directly also works: CORS allows localhost:5173 and localhost:3000. Other origins go in
`CORS_ORIGINS` in `backend/.env`.

## The session flow the UI drives
1. `POST /api/plans` -> `plan_id`
2. `POST /api/sessions` with `consent: true` -> `session_id`, `pair_code` (show it for the iPad)
3. Voice on `WS /ws/voice/{session_id}` (typed fallback: `POST /api/sessions/{id}/turns`)
4. Circuit on `WS /ws/board/{session_id}` (`probe` -> `probe_result`; the iPad sends `pair` first)
5. `POST /api/sessions/{id}/end` returns at once -> listen on `GET /api/sessions/{id}/events` (SSE) until `grading_complete`
6. `GET /api/sessions/{id}/report`, `GET /api/lessons/{skill_id}`, `POST /api/retests`, `GET /api/mastery?user_id=`
7. Consent: `DELETE /api/sessions/{id}` removes everything for a tester

## What is real vs stubbed today
Real: sessions, consent, pair codes, answers stored, probe events with server-side seq and readings from scenario
files, grading pipeline + SSE (runs when a rubric is marked `reviewed`), mastery, metrics, deletion, WebSocket message routing.
Stubbed: interviewer replies (text says TODO), speech-to-text and TTS audio, the evaluator model call,
plan generation, lessons content, vision critique. Endpoints keep their shapes when these are filled in.

## Deploy
Either host the React build and the API as two services (set `CORS_ORIGINS` to the frontend's URL), or put
both behind one reverse proxy that sends `/api/*` and `/ws/*` to the backend and everything else to the React files.

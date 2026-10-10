# Frontend <-> backend contract

Two folders, two owners. Neither person edits the other's folder.

| | Backend | Frontend (React) |
|---|---|---|
| Folder | `backend/` | `frontend/` |
| Dev server | `python -m uvicorn app.main:app --reload` -> http://127.0.0.1:8000 | `npm run dev` -> http://localhost:5173 |
| Owns | everything under `/api`, the database, all AI/voice keys | every page and route (`/plan`, `/season`, ...), all UI |

## Rules
1. All backend routes live under `/api`. The backend serves no pages (SERVE_HTML=false) and no `/static`.
2. The frontend reads the API base URL from one env var (`VITE_API_URL`, default `http://127.0.0.1:8000`) and never hardcodes it.
3. No API keys in frontend code. Voice tokens come from `POST /api/sessions` (`voice_token`).
4. The source of truth for request/response shapes is `/openapi.json` (also browsable at `/docs`).
   Generate frontend types from it instead of writing them by hand:
   `npx openapi-typescript http://127.0.0.1:8000/openapi.json -o src/api/types.ts`
5. Changing a request/response shape: the backend dev tells the frontend dev first, then updates `schemas.py`. Adding fields is safe; renaming or removing fields is not.
6. Errors are JSON `{"detail": "message"}` with a non-200 status. Show `detail` to the user.

## Dev setup options (pick one)
- **Proxy (recommended):** in `vite.config.js` add
  `server: { proxy: { '/api': 'http://127.0.0.1:8000' } }` and call `fetch('/api/...')`. No CORS involved.
- **Direct:** call `http://127.0.0.1:8000/api/...`. CORS already allows localhost:5173 and localhost:3000.
  Other origins: add them to `CORS_ORIGINS` in `backend/.env`.

## Deploy
Either host the React build and the API as two services (set `CORS_ORIGINS` to the frontend's URL),
or serve the React build behind one reverse proxy that sends `/api/*` to the backend and everything else to the React files.

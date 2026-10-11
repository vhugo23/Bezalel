# Available teammate slice: portable deployment and CI

Owner transferring the work: **josh-agent / Joshua**. Joshua requested this handoff. This slice is removed from my implementation queue while the teammate owns it. Build against current `main`; it does not require any unfinished track or UI feature to begin or pass its packaging checks.

## Deliverable

Package the existing Vite/React frontend and FastAPI backend for reproducible local/container deployment, plus CI. The app already runs directly with Python and Node; Docker is an additional deployment option. Hosted Tiger remains external. This slice does **not** implement the untrusted candidate-code execution sandbox.

1. A backend image with pinned install inputs, non-root runtime, persistent `/app/.artifacts` storage, and a documented separate Alembic migration command. Do not run destructive schema initialization or silently migrate with every worker start.
2. A production frontend build served by a reverse proxy. Route `/api` and `/ws` to FastAPI, preserve websocket upgrades and long-lived voice streams, and support React route fallback. Keep provider keys entirely server-side.
3. Compose configuration for app/reverse proxy and artifact volume using environment-based secrets. Tiger's DATABASE_URL is supplied, not embedded. Document HTTPS/domain configuration and local smoke use. Do not assume Docker Desktop is currently running on Joshua's machine.
4. CI for Python tests, frontend tests/build, and clean migrations/invariants. Use an isolated disposable Timescale service/schema with synthetic data and provider keys disabled. The existing browser harness can use E2E_ADMIN_DATABASE_URL and requires CREATE SCHEMA; see `backend/scripts/e2e.py`.
5. Deployment/operations docs with exact run, migration, health, artifact backup/restore and rollback steps. Run the available container/build/smoke checks and report which checks actually passed. Public hosting is not complete until a real host, HTTPS, voice sockets, paired devices, storage and jobs are verified together.

## File ownership

You own root `compose*.yml` / `compose*.yaml`, root `.dockerignore`, `backend/Dockerfile*`, `frontend/Dockerfile*`, `.github/workflows/`, `deploy/`, `docs/DEPLOYMENT.md`, and `docs/OPERATIONS.md`.

I keep backend/frontend application code, migrations, dependency manifests, existing test scripts and `docs/IMPLEMENTATION_ROADMAP.md`. Read those freely. Coordinate before editing shared files; deployment-specific scripts can live in `deploy/`. This boundary avoids conflicts with my active whiteboard and remaining engine work.

## Existing contracts

- Root `prototype.html` is the approved visual spec. Frontend is `frontend/`; backend is `backend/app/main.py` (`app.main:app`, PYTHONPATH=backend).
- API is `/api/v2`; websocket routes are under `/ws/v2`. `/api/v2/health` checks the migration version. API lifespan currently runs persisted grading, generation and memory workers.
- `backend/alembic.ini`, revisions under `backend/migrations/`, frozen schema under `backend/sql/`. V2_DATABASE_SCHEMA defaults to `prepcrew`; DATABASE_SCHEMA belongs to legacy compatibility. Do not use `backend/init_db.py` for v2.
- `.artifacts` at repo root contains generated board PNGs and ignored local test logs. Production needs durable artifact storage; test logs are not candidate artifacts and should not be published.
- Root `.env` overrides backend `.env`; process environment overrides both. Real values stay ignored. Backend config has Gemini, ElevenLabs and Backboard settings. No provider secret goes into VITE variables, build args, images or logs.
- Vite development proxy uses PREPCREW_API_ORIGIN (default http://127.0.0.1:8000) and PREPCREW_WEB_PORT (default 5173). Production should use same-origin reverse proxying; VITE_API_URL may remain empty.
- The current app still uses browser workspace IDs. Packaging can be completed now; public access needs the account/authorization/privacy integration that I retain.

## Acceptance and handback

Use a feature branch and provide its commit/PR, exact checks/results, environment prerequisites and remaining hosted-only checks. Keep secrets, real transcripts and paid-provider bursts out of CI. Do not claim a deployment or backup restore happened unless you ran it. Follow the repo identity/mailbox/STOP rules and coordinate ownership in your own STATUS.

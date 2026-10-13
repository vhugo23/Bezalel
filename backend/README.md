# PrepCrew backend

FastAPI on Python 3.11+, ordinary PostgreSQL and authenticated HTTP/WebSockets. Use `npm run setup` and `npm start` from the repository root for the supported single-app launcher; it manages native Postgres and serves the built React app at the same origin. Docker is not required.

Current services live in `app/v2`. Per-account connections select Gemini, OpenAI, Anthropic or compatible model transports and local/cloud speech. The API owns encrypted credentials, session ownership, event evidence, assessments and persisted jobs. Use one API worker. Legacy prototypes and opt-in Backboard/Timescale adapters remain for compatibility.

For direct development, set `DATABASE_URL`, `V2_DATABASE_SCHEMA` and `PYTHONPATH=backend`, run `python -m alembic -c backend/alembic.ini upgrade head`, then `python -m uvicorn app.main:app`. Do not run the historical `init_db.py` for the current app. See the root README and docs/PORTFOLIO.md for storage, hosting and provider boundaries.

Run `python -m pytest backend/tests -q` with `PYTHONPATH=backend`. Browser acceptance uses `backend/scripts/e2e.py` and a disposable schema in a local `E2E_ADMIN_DATABASE_URL`; it never needs paid provider keys. API documentation is at `/docs`.

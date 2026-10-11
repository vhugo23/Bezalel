# v2.3 migration boundary

The configured Tiger Data database contained legacy `public.users`, `public.sessions`, `public.memories`, and generic `records`/`events`. Migration 001 installs the approved v2.3 SQL in the separate `prepcrew` schema. Existing rows and legacy endpoints are preserved. The React application calls `/api/v2/*` and uses only the new schema.

`sql/001_v23.sql` is a frozen copy of the approved `backend/sql/prepcrew.sql`. Future changes must be new revisions. Do not run `init_db.py` to migrate v2.3: it mixes the older public-schema tables with the new model.

Migration 002 pins the assessment trigger's search path and prevents late assessments from replacing newer mastery. The configured cloud service reported TimescaleDB 2.30.2. Both migrations have run successfully there.

Run from the repo root:

```powershell
.\.venv\Scripts\python -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python backend/scripts/verify_v23.py
```

No compression policy is installed. All event references from claims and annotations remain soft references. Destructive downgrades are deliberately unsupported.

`V2_DATABASE_SCHEMA` defaults to `prepcrew`. A validated identifier can select an
isolated schema for acceptance tests; migrations and the application use the
same namespace, including trigger search paths and aggregate metadata queries.
The frozen SQL and default production schema are unchanged.

Run `python backend/scripts/e2e.py` through the repository virtual environment
after installing Playwright Chromium (`cd frontend; npx playwright install chromium`).
The runner creates a uniquely named `prepcrew_e2e_*` schema, migrates it from zero,
starts its own demo API and frontend on ports 18000/15173, disables provider keys,
runs browser tests, stops its child processes and drops only that schema. Logs
and traces stay ignored. The normal `prepcrew` records are never test fixtures.

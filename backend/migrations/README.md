# Database migrations

The current app uses the isolated `prepcrew` PostgreSQL schema. The legacy public-schema application is disabled by default. Do not use `init_db.py` for the current app.

New installs use ordinary PostgreSQL tables and views. Migration 001 renders the frozen hackathon schema through `app/postgres_schema.py`, replacing only Timescale extension installation, hypertable conversion and continuous aggregates. All subsequent revisions apply unchanged. The two analytical views show fresh data immediately.

`DATABASE_TIMESCALE=true` explicitly preserves the original Timescale installation path for a new Timescale database. Existing installations already at migration head are unaffected: changing the flag does not convert existing hypertables, views or records. Use a separate new database for the portable local setup; no automated production conversion is included.

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python -m alembic -c backend/alembic.ini upgrade head
```

`DATABASE_URL` selects the database. `V2_DATABASE_SCHEMA` defaults to `prepcrew`; migration and application search paths must match. Destructive downgrades are disabled.

`npm start` manages native local Postgres and applies migrations automatically. `backend/scripts/e2e.py` creates a uniquely named disposable schema, migrates it from zero, runs synthetic acceptance checks and browser journeys, then removes only that test schema. `verify_v23.py` is the historical Timescale-specific verifier; use the portable acceptance runner for standard Postgres.

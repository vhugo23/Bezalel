-- CORE tables: idea-agnostic. Safe to run repeatedly.

-- JSON documents grouped by kind (users, projects, sessions, anything)
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    owner_id TEXT,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS records_kind_idx ON records (kind, created_at DESC);

-- Time-series rows per subject (scores, readings, anything measured over time)
CREATE TABLE IF NOT EXISTS events (
    subject_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    value DOUBLE PRECISION,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS events_subject_idx ON events (subject_id, kind, created_at DESC);
-- If your Tiger Data instance supports hypertables, convert it (run once, ignore errors):
-- SELECT create_hypertable('events', 'created_at', if_not_exists => TRUE, migrate_data => TRUE);

-- Long-term memory (used when MEMORY_BACKEND=postgres)
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    text TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS memories_owner_idx ON memories (owner_id, created_at DESC);

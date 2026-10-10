-- PrepCrew module tables. Same as the first skeleton, so re-running changes nothing.
-- A different idea can ignore this file (or delete it) and use records/events instead.

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    plan_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS turns (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS topics (
    id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS lessons (
    topic_id TEXT PRIMARY KEY,
    body TEXT,
    ai_generated BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS evaluations (
    session_id TEXT,
    evaluator TEXT,
    topic_id TEXT,
    score DOUBLE PRECISION,
    evidence TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

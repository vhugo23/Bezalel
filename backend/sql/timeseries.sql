-- Tiger Data time-series (from contracts/db.sql). Two hypertables and a continuous aggregate for the mastery chart.
-- No foreign keys on purpose: hypertables are deleted by session_id (consent), and the app keeps its sessions in
-- the generic records table. Idempotent: safe to re-run. Needs the timescaledb extension (Tiger has it).

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- One row per graded criterion. score is normalized to 0..1 (criterion score / rubric score_max).
CREATE TABLE IF NOT EXISTS answer_scores (
    time         TIMESTAMPTZ NOT NULL,
    user_id      TEXT        NOT NULL,
    session_id   TEXT        NOT NULL,
    answer_id    TEXT        NOT NULL,
    module       TEXT        NOT NULL,   -- interview | debug | drill | embedded_c | behavioral
    skill_id     TEXT        NOT NULL,
    criterion_id TEXT        NOT NULL,
    score        REAL        NOT NULL CHECK (score >= 0 AND score <= 1),
    source       TEXT        NOT NULL,   -- evaluator | retest | hand_grade
    needs_review BOOLEAN     NOT NULL DEFAULT FALSE
);
SELECT create_hypertable('answer_scores', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS answer_scores_user_skill ON answer_scores (user_id, skill_id, time DESC);
CREATE INDEX IF NOT EXISTS answer_scores_session ON answer_scores (session_id);

-- One row per action on the circuit (contracts/probe_event.schema.json). seq is assigned by the server.
CREATE TABLE IF NOT EXISTS probe_events (
    time        TIMESTAMPTZ NOT NULL,
    event_id    TEXT        NOT NULL,
    seq         INTEGER     NOT NULL,
    session_id  TEXT        NOT NULL,
    scenario_id TEXT        NOT NULL,
    action      TEXT        NOT NULL,
    node        TEXT,
    value       REAL,
    unit        TEXT
);
SELECT create_hypertable('probe_events', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS probe_events_session ON probe_events (session_id, seq);

-- Daily mastery per user and skill; GET /api/mastery reads this. Real-time (materialized_only = false) so a score
-- shows up immediately, not after the next refresh. Rows that need review never move the chart.
CREATE MATERIALIZED VIEW IF NOT EXISTS mastery_daily
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT time_bucket(INTERVAL '1 day', time) AS day,
       user_id,
       skill_id,
       avg(score) AS mastery,
       count(*)   AS n
FROM answer_scores
WHERE needs_review = FALSE
GROUP BY time_bucket(INTERVAL '1 day', time), user_id, skill_id
WITH NO DATA;
SELECT add_continuous_aggregate_policy('mastery_daily',
    start_offset => INTERVAL '3 days', end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 minute', if_not_exists => TRUE);

-- PrepCrew time-series contract for Tiger Data (TimescaleDB).
-- UNVERIFIED: hypertable and continuous aggregate syntax below is from memory. Run the Tiger Data
-- spike against the real free-tier service and fix anything that errors before relying on this.
-- Newer Tiger Data docs may prefer CREATE TABLE ... WITH (tsdb.hypertable ...). Check the docs.
-- Does not replace backend/sql/prepcrew.sql. See contracts/README.md for the overlap with `evaluations`.

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- One row per criterion per answer. score is normalized to 0..1 (criterion score / rubric score_max).
CREATE TABLE IF NOT EXISTS answer_scores (
    time        TIMESTAMPTZ NOT NULL,
    user_id     TEXT        NOT NULL,
    session_id  TEXT        NOT NULL,
    answer_id   TEXT        NOT NULL,
    module      TEXT        NOT NULL,   -- interview | debug | drill | embedded_c | behavioral
    skill_id    TEXT        NOT NULL,   -- from the rubric criterion
    criterion_id TEXT       NOT NULL,
    score       REAL        NOT NULL CHECK (score >= 0 AND score <= 1),
    source      TEXT        NOT NULL,   -- evaluator | retest | hand_grade
    needs_review BOOLEAN    NOT NULL DEFAULT FALSE
);
SELECT create_hypertable('answer_scores', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS answer_scores_user_skill ON answer_scores (user_id, skill_id, time DESC);
CREATE INDEX IF NOT EXISTS answer_scores_session ON answer_scores (session_id);

-- One row per user action on the circuit. Mirrors contracts/probe_event.schema.json.
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

-- Daily mastery per user and skill. The mastery chart reads this view.
-- Rows with needs_review are left out so unchecked grades never move the chart.
CREATE MATERIALIZED VIEW IF NOT EXISTS mastery_daily
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 day', time) AS day,
       user_id,
       skill_id,
       avg(score)  AS mastery,
       count(*)    AS n
FROM answer_scores
WHERE needs_review = FALSE
GROUP BY day, user_id, skill_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('mastery_daily',
    start_offset => INTERVAL '3 days',
    end_offset   => INTERVAL '0 minutes',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE);

-- Consent and deletion. Hypertables do not take foreign keys, so deleting a tester session is explicit.
-- After deleting, refresh the aggregate for the affected range so the chart drops that data.
-- DELETE FROM answer_scores WHERE session_id = $1;
-- DELETE FROM probe_events  WHERE session_id = $1;
-- CALL refresh_continuous_aggregate('mastery_daily', NULL, NULL);

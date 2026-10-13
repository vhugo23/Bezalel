"""Portable rendering of the frozen hackathon schema for new installations.

Existing Timescale installations keep their history. Only the three storage
optimizations and two analytical views differ; application tables stay identical.
"""
import re


def portable_schema(sql: str) -> str:
    sql = sql.replace('CREATE EXTENSION IF NOT EXISTS timescaledb;', '')
    sql = re.sub(r"^SELECT create_hypertable\([^\n]+\);\s*$", '', sql, flags=re.M)
    start = sql.index('CREATE MATERIALIZED VIEW IF NOT EXISTS mastery_hourly')
    end = sql.index('-- 15. SEED', start)
    # Ordinary views include newly written assessments immediately, without a
    # scheduler, extension permissions, or a materialized-view refresh worker.
    views = """CREATE OR REPLACE VIEW mastery_hourly AS
SELECT user_id, skill_id, date_trunc('hour', ts) AS bucket,
       (array_agg(score ORDER BY ts DESC))[1] AS score,
       max(score) AS best, count(*) AS samples
FROM skill_assessments WHERE NOT is_estimate
GROUP BY user_id, skill_id, date_trunc('hour', ts);

CREATE OR REPLACE VIEW latency_1m AS
SELECT name, date_trunc('minute', ts) AS bucket,
       count(*) AS n, avg(value) AS avg, min(value) AS min, max(value) AS max
FROM metrics WHERE name LIKE '%\\_ms' ESCAPE '\\'
GROUP BY name, date_trunc('minute', ts);

"""
    return sql[:start] + views + sql[end:]

"""Tiger Data time-series (sql/timeseries.sql): answer_scores and probe_events hypertables, and the mastery_daily
continuous aggregate behind GET /api/mastery. Active only when DATABASE_URL is set.

Every call is best effort: a missing table (init_db not run), a slow database or any other error is logged and
the app carries on, because the same data is also kept in the generic events table."""
import asyncio
import logging
from datetime import datetime, timezone

from app import config, db

log = logging.getLogger("prepcrew.timeseries")
TIMEOUT_SECONDS = 3
_missing: set[str] = set()  # tables found missing once; stop trying until restart


def enabled() -> bool:
    return bool(config.DATABASE_URL)


def _when(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.now(timezone.utc)


async def _run(name: str, fn):
    if not enabled() or name in _missing:
        return None
    try:
        return await asyncio.wait_for(fn(), TIMEOUT_SECONDS)
    except Exception as e:
        if "does not exist" in str(e):
            _missing.add(name)
            log.warning("%s is missing; run init_db.py to create sql/timeseries.sql (%s)", name, e)
        else:
            log.warning("time-series %s failed: %s: %s", name, type(e).__name__, e)
        return None


async def write_probe(event: dict) -> bool:
    async def go():
        await db.execute(
            "insert into probe_events (time, event_id, seq, session_id, scenario_id, action, node, value, unit) "
            "values ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
            _when(event.get("t")), event["event_id"], event["seq"], event["session_id"], event["scenario_id"],
            event["action"], event.get("node"), event.get("value"), event.get("unit"))
        return True
    return bool(await _run("probe_events", go))


async def write_scores(rows: list[dict]) -> int:
    """rows: {user_id, session_id, answer_id, module, skill_id, criterion_id, score (0..1), source, needs_review}"""
    if not rows:
        return 0

    async def go():
        now = datetime.now(timezone.utc)
        for r in rows:
            await db.execute(
                "insert into answer_scores (time, user_id, session_id, answer_id, module, skill_id, criterion_id, "
                "score, source, needs_review) values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
                now, r["user_id"], r["session_id"], r["answer_id"], r["module"], r["skill_id"], r["criterion_id"],
                max(0.0, min(1.0, float(r["score"]))), r["source"], bool(r["needs_review"]))
        return len(rows)
    return await _run("answer_scores", go) or 0


async def mastery_series(user_id: str) -> list[dict] | None:
    """Series per skill from mastery_daily, or None when the aggregate is unavailable (caller falls back)."""
    async def go():
        rows = await db.fetch("select day, skill_id, mastery, n from mastery_daily where user_id = $1 "
                              "order by skill_id, day", user_id)
        series: dict[str, list[dict]] = {}
        for r in rows:
            series.setdefault(r["skill_id"], []).append(
                {"day": r["day"].date().isoformat(), "mastery": float(r["mastery"]), "n": int(r["n"])})
        return [{"skill_id": k, "points": v} for k, v in series.items()]
    return await _run("mastery_daily", go)


async def delete_session(session_id: str) -> int:
    """Consent deletion: remove the session's rows, then refresh the aggregate so the chart drops them too."""
    async def go():
        removed = 0
        for table in ("answer_scores", "probe_events"):
            removed += int((await db.execute(f"delete from {table} where session_id = $1", session_id)).split()[-1])
        try:
            await db.execute("CALL refresh_continuous_aggregate('mastery_daily', NULL, NULL)")
        except Exception as e:  # plain Postgres in tests, or no aggregate: rows are gone either way
            log.info("mastery_daily refresh skipped: %s", e)
        return removed
    return await _run("answer_scores", go) or 0

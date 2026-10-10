"""Generic storage any idea can use without new tables:
  records: JSON documents grouped by `kind`   (users, projects, sessions, anything)
  events:  time-series rows per subject       (scores, readings, clicks, anything)
Uses Postgres when DATABASE_URL is set, otherwise in-memory so everything runs with no setup."""
import uuid
from datetime import datetime, timezone

from app import config, db

_records: dict[str, dict] = {}
_events: list[dict] = []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _use_db() -> bool:
    return bool(config.DATABASE_URL)


def _row(row) -> dict:
    d = dict(row)
    if d.get("created_at") is not None:
        d["created_at"] = d["created_at"].isoformat()
    return d


# ---- records ----
async def create_record(kind: str, data: dict, owner_id: str | None = None) -> dict:
    rid = str(uuid.uuid4())
    if _use_db():
        row = await db.fetchrow(
            "insert into records (id, kind, owner_id, data) values ($1, $2, $3, $4) "
            "returning id, kind, owner_id, data, created_at",
            rid, kind, owner_id, data,
        )
        return _row(row)
    rec = {"id": rid, "kind": kind, "owner_id": owner_id, "data": data, "created_at": _now()}
    _records[rid] = rec
    return rec


async def get_record(record_id: str) -> dict | None:
    if _use_db():
        row = await db.fetchrow(
            "select id, kind, owner_id, data, created_at from records where id = $1", record_id)
        return _row(row) if row else None
    return _records.get(record_id)


async def list_records(kind: str, owner_id: str | None = None, limit: int = 50) -> list[dict]:
    if _use_db():
        rows = await db.fetch(
            "select id, kind, owner_id, data, created_at from records "
            "where kind = $1 and ($2::text is null or owner_id = $2) "
            "order by created_at desc limit $3",
            kind, owner_id, limit,
        )
        return [_row(r) for r in rows]
    items = [r for r in _records.values() if r["kind"] == kind and (owner_id is None or r["owner_id"] == owner_id)]
    return sorted(items, key=lambda r: r["created_at"], reverse=True)[:limit]


async def update_record(record_id: str, data: dict) -> dict | None:
    """Merges `data` into the existing document (top-level keys)."""
    if _use_db():
        row = await db.fetchrow(
            "update records set data = data || $2::jsonb where id = $1 "
            "returning id, kind, owner_id, data, created_at",
            record_id, data,
        )
        return _row(row) if row else None
    rec = _records.get(record_id)
    if rec:
        rec["data"] = {**rec["data"], **data}
    return rec


# ---- events (time-series) ----
async def add_event(subject_id: str, kind: str, value: float | None = None, data: dict | None = None) -> dict:
    data = data or {}
    if _use_db():
        row = await db.fetchrow(
            "insert into events (subject_id, kind, value, data) values ($1, $2, $3, $4) "
            "returning subject_id, kind, value, data, created_at",
            subject_id, kind, value, data,
        )
        return _row(row)
    ev = {"subject_id": subject_id, "kind": kind, "value": value, "data": data, "created_at": _now()}
    _events.append(ev)
    return ev


async def list_events(subject_id: str, kind: str | None = None, limit: int = 200) -> list[dict]:
    if _use_db():
        rows = await db.fetch(
            "select subject_id, kind, value, data, created_at from events "
            "where subject_id = $1 and ($2::text is null or kind = $2) "
            "order by created_at desc limit $3",
            subject_id, kind, limit,
        )
        return [_row(r) for r in rows]
    items = [e for e in _events if e["subject_id"] == subject_id and (kind is None or e["kind"] == kind)]
    return sorted(items, key=lambda e: e["created_at"], reverse=True)[:limit]


# ---- deletion (consent: remove everything tied to one id) ----
async def delete_linked(subject_id: str) -> int:
    """Deletes the record with this id, records whose data.session_id is this id, and all events for it.
    Returns how many rows were removed."""
    if _use_db():
        r1 = await db.execute("delete from events where subject_id = $1", subject_id)
        r2 = await db.execute(
            "delete from records where id = $1 or data->>'session_id' = $1", subject_id)
        return int(r1.split()[-1]) + int(r2.split()[-1])
    global _events
    before = len(_events)
    _events = [e for e in _events if e["subject_id"] != subject_id]
    removed = before - len(_events)
    for rid in [rid for rid, r in _records.items()
                if rid == subject_id or r["data"].get("session_id") == subject_id]:
        del _records[rid]
        removed += 1
    return removed

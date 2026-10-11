"""Long-term memory: remember(owner, text) / recall(owner, query) / forget(refs).

Backends (MEMORY_BACKEND):
  "backboard"  Backboard (https://docs.backboard.io). One Backboard assistant per owner, because Backboard scopes
               memory to an assistant. Any Backboard failure falls back to the local backend, so memory never
               breaks a session.
  "postgres"   the memories table.   "memory"  in-process (lost on restart).
  blank        postgres if DATABASE_URL is set, else memory.

remember() returns a ref {"backend", "id", "assistant_id"} so callers can delete exactly what they stored
(consent deletion). Pass refs to forget().
"""
import asyncio
import logging
import uuid
from collections import defaultdict

from app import config, db

log = logging.getLogger("core.memory")

_mem: dict[str, list[dict]] = {}                      # memory backend: owner -> [{"id", "text"}]
_assistant_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_transport = None                                    # tests inject an httpx transport here
TIMEOUT_SECONDS = 8


class BackboardError(Exception):
    pass


def _backend() -> str:
    return config.MEMORY_BACKEND or _local_backend()


def _local_backend() -> str:
    return "postgres" if config.DATABASE_URL else "memory"


# ---------------- local backends ----------------
async def _local_remember(owner_id: str, text: str, data: dict | None) -> dict:
    mid = str(uuid.uuid4())
    if _local_backend() == "postgres":
        await db.execute("insert into memories (id, owner_id, text, data) values ($1, $2, $3, $4)",
                         mid, owner_id, text, data or {})
        return {"backend": "postgres", "id": mid, "assistant_id": None}
    _mem.setdefault(owner_id, []).append({"id": mid, "text": text})
    return {"backend": "memory", "id": mid, "assistant_id": None}


async def _local_recall(owner_id: str, limit: int) -> list[str]:
    if _local_backend() == "postgres":
        rows = await db.fetch("select text from memories where owner_id = $1 order by created_at desc limit $2",
                              owner_id, limit)
        return [r["text"] for r in rows]
    return [m["text"] for m in _mem.get(owner_id, [])[-limit:][::-1]]


async def _local_forget(ref: dict) -> int:
    if ref["backend"] == "postgres":
        return int((await db.execute("delete from memories where id = $1", ref["id"])).split()[-1])
    for items in _mem.values():
        for i, m in enumerate(items):
            if m["id"] == ref["id"]:
                del items[i]
                return 1
    return 0


# ---------------- Backboard ----------------
def _client():
    import httpx  # lazy import
    return httpx.AsyncClient(base_url=config.BACKBOARD_BASE_URL, timeout=TIMEOUT_SECONDS, transport=_transport,
                             headers={"X-API-Key": config.BACKBOARD_API_KEY})


async def _bb(method: str, path: str, **kwargs) -> dict:
    if not config.BACKBOARD_API_KEY:
        raise BackboardError("BACKBOARD_API_KEY is empty")
    async with _client() as c:
        resp = await c.request(method, path, **kwargs)
    if resp.status_code >= 300:
        err = BackboardError(f"Backboard {method} {path.split('/')[1]} -> {resp.status_code}: {resp.text[:200]}")
        err.status = resp.status_code
        raise err
    return resp.json() if resp.content else {}


async def _assistant_for(owner_id: str) -> str:
    """The owner's Backboard assistant, created on first use. The mapping is kept in core.store."""
    from app.core import store  # local import: store imports db too, avoid cycles at import time
    async with _assistant_locks[owner_id]:
        found = await store.find_records("bb_assistant", "owner_id", owner_id, limit=1)
        if found:
            return found[0]["data"]["assistant_id"]
        out = await _bb("POST", "/assistants", json={
            "name": f"PrepCrew candidate {owner_id[:80]}",
            "system_prompt": "Memory store for one PrepCrew interview candidate: gaps and strengths from past sessions."})
        aid = out.get("assistant_id") or out.get("id")
        if not aid:
            raise BackboardError(f"create assistant returned no id (keys: {sorted(out)})")
        await store.create_record("bb_assistant", {"owner_id": owner_id, "assistant_id": aid}, owner_id=owner_id)
        return aid


def _memory_id(out: dict) -> str | None:
    """Backboard's docs do not show the add-memory response, so accept the likely shapes."""
    for key in ("memory_id", "id"):
        if out.get(key):
            return str(out[key])
    inner = out.get("memory") or {}
    return str(inner["id"]) if isinstance(inner, dict) and inner.get("id") else None


# ---------------- public API ----------------
async def remember(owner_id: str, text: str, data: dict | None = None) -> dict:
    if _backend() == "backboard":
        try:
            aid = await _assistant_for(owner_id)
            out = await _bb("POST", f"/assistants/{aid}/memories", json={"content": text, "metadata": data or {}})
            mid = _memory_id(out)
            if mid is None:
                log.warning("Backboard add memory returned no id (keys: %s); it cannot be deleted one by one", sorted(out))
            return {"backend": "backboard", "id": mid, "assistant_id": aid}
        except Exception as e:  # never let memory break a session
            log.warning("Backboard remember failed, using %s: %s", _local_backend(), e)
    return await _local_remember(owner_id, text, data)


async def recall(owner_id: str, query: str = "", limit: int = 10) -> list[str]:
    """Most relevant memories for `query` (Backboard search), or the most recent ones without a query."""
    if _backend() == "backboard":
        try:
            from app.core import store
            found = await store.find_records("bb_assistant", "owner_id", owner_id, limit=1)
            if not found:
                return await _local_recall(owner_id, limit)  # never used Backboard: maybe a local fallback exists
            aid = found[0]["data"]["assistant_id"]
            if query.strip():
                out = await _bb("POST", f"/assistants/{aid}/memories/search",
                                json={"query": query[:2000], "limit": max(1, min(limit, 50))})
            else:
                out = await _bb("GET", f"/assistants/{aid}/memories", params={"page": 1, "page_size": max(1, min(limit, 100))})
            texts = [m.get("content", "") for m in out.get("memories", []) if m.get("content")]
            return texts[:limit] + [t for t in await _local_recall(owner_id, limit) if t not in texts][: max(0, limit - len(texts))]
        except Exception as e:
            log.warning("Backboard recall failed, using %s: %s", _local_backend(), e)
    return await _local_recall(owner_id, limit)


async def forget(refs: list[dict]) -> int:
    """Delete exactly the memories these refs point at. Returns how many were removed. Never raises."""
    removed, _failed = await forget_detailed(refs)
    return removed


async def forget_detailed(refs: list[dict]) -> tuple[int, list[dict]]:
    """Like forget(), but also returns the refs that could not be deleted (e.g. Backboard was down), so the caller
    can keep them and try again later instead of losing track of data that must be deleted."""
    removed, failed = 0, []
    for ref in refs:
        try:
            if ref.get("backend") == "backboard":
                if ref.get("id") and ref.get("assistant_id"):
                    try:
                        await _bb("DELETE", f"/assistants/{ref['assistant_id']}/memories/{ref['id']}")
                        removed += 1
                    except BackboardError as e:
                        if getattr(e, "status", None) != 404:  # 404: already gone, which is what we wanted
                            raise
            elif ref.get("id"):
                removed += await _local_forget(ref)
        except Exception as e:
            log.warning("forget failed for one memory (%s): %s", ref.get("backend"), e)
            failed.append(ref)
    return removed, failed

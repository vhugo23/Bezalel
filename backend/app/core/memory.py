"""Neutral memory layer: remember(owner, text) / recall(owner).
Backends: "memory" (in-process, lost on restart), "postgres" (memories table), "backboard" (TODO).
The built-in backends return the most recent items; `query` is reserved for smarter backends."""
import uuid

from app import config, db

_mem: dict[str, list[str]] = {}


def _backend() -> str:
    return config.MEMORY_BACKEND or ("postgres" if config.DATABASE_URL else "memory")


async def remember(owner_id: str, text: str, data: dict | None = None) -> None:
    backend = _backend()
    if backend == "memory":
        _mem.setdefault(owner_id, []).append(text)
    elif backend == "postgres":
        await db.execute(
            "insert into memories (id, owner_id, text, data) values ($1, $2, $3, $4)",
            str(uuid.uuid4()), owner_id, text, data or {},
        )
    else:
        raise NotImplementedError(f"memory backend '{backend}' is not implemented yet (TODO: Backboard)")


async def recall(owner_id: str, query: str = "", limit: int = 10) -> list[str]:
    backend = _backend()
    if backend == "memory":
        return _mem.get(owner_id, [])[-limit:][::-1]
    if backend == "postgres":
        rows = await db.fetch(
            "select text from memories where owner_id = $1 order by created_at desc limit $2",
            owner_id, limit,
        )
        return [r["text"] for r in rows]
    raise NotImplementedError(f"memory backend '{backend}' is not implemented yet (TODO: Backboard)")

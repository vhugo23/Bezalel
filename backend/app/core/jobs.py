"""Run several async tasks at once with a per-task timeout and an optional concurrency limit.
One failure never loses the others."""
import asyncio
import time
from typing import Any, Awaitable, Callable

from app import config


async def _run_one(fn: Callable[[], Awaitable[Any]], timeout: float, sem: asyncio.Semaphore | None) -> dict:
    async def guarded():
        if sem is None:
            return await fn()
        async with sem:
            return await fn()

    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(guarded(), timeout=timeout)
        ok, error = True, None
    except Exception as e:  # includes timeouts
        result, ok, error = None, False, f"{type(e).__name__}: {e}"
    return {
        "ok": ok,
        "result": result,
        "error": error,
        "duration_ms": int((time.perf_counter() - start) * 1000),
    }


async def fan_out(
    tasks: dict[str, Callable[[], Awaitable[Any]]],
    timeout: float | None = None,
    limit: int | None = None,
) -> dict[str, dict]:
    """tasks = {name: zero-arg async function}. Returns {name: {ok, result, error, duration_ms}}.
    `limit` caps how many run at the same time (a semaphore); None means no cap.
    The timeout covers waiting for a free slot plus running."""
    timeout = timeout or config.TASK_TIMEOUT_SECONDS
    sem = asyncio.Semaphore(limit) if limit else None
    names = list(tasks)
    outcomes = await asyncio.gather(*(_run_one(tasks[n], timeout, sem) for n in names))
    return dict(zip(names, outcomes))

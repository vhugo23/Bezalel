"""Run several async tasks at once with a per-task timeout. One failure never loses the others."""
import asyncio
import time
from typing import Any, Awaitable, Callable

from app import config


async def _run_one(fn: Callable[[], Awaitable[Any]], timeout: float) -> dict:
    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(fn(), timeout=timeout)
        ok, error = True, None
    except Exception as e:  # includes timeouts
        result, ok, error = None, False, f"{type(e).__name__}: {e}"
    return {
        "ok": ok,
        "result": result,
        "error": error,
        "duration_ms": int((time.perf_counter() - start) * 1000),
    }


async def fan_out(tasks: dict[str, Callable[[], Awaitable[Any]]], timeout: float | None = None) -> dict[str, dict]:
    """tasks = {name: zero-arg async function}. Returns {name: {ok, result, error, duration_ms}}."""
    timeout = timeout or config.TASK_TIMEOUT_SECONDS
    names = list(tasks)
    outcomes = await asyncio.gather(*(_run_one(tasks[n], timeout) for n in names))
    return dict(zip(names, outcomes))

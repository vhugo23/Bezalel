"""One quick retry when the model provider says it is busy. Used by the plan call, the live reply and the gap check.
Each caller keeps its own overall time limit (asyncio.wait_for around this), so a retry cannot run past it.

Backup model (with_backup below): when the primary model is still busy or times out after that one retry, the same
call is tried once on a second model before the caller falls back to its planned question. The second model's name
comes from the environment variable GEMINI_BACKUP_MODEL. It is read here, with os.getenv, because core/ai.py and
config.py are not lane 1 files. Blank, missing or the same as GEMINI_MODEL means no backup: the code then makes exactly the
calls it made before this existed (same arguments, same retry, same time limit).

Time: the call's existing limit T (LIVE_TURN_TIMEOUT_SECONDS for a live turn, ASSESSOR_TIMEOUT_SECONDS for the gap
check, TASK_TIMEOUT_SECONDS for the plan) stays the limit for primary plus backup together. The primary, with its one
retry, gets at most PRIMARY_SHARE of T. The backup gets whatever is left of T, which is at least the rest of the share
and is more when the primary failed early. So a backup never makes a call slower than T, which is the worst case
that already existed."""
import asyncio
import logging
import os

from app import config
from app.core import ai

log = logging.getLogger("prepcrew.retry")

TRANSIENT = ("error 503", "error 429", "error 500", "error 502", "error 504")

BACKUP_ENV = "GEMINI_BACKUP_MODEL"
# Share of a call's time limit the primary model may use before the backup gets its turn. 0.6 leaves the backup at
# least 40 percent: 2.0 s of the 5 s live turn and 1.6 s of the 4 s gap check, where spikes/RESULTS.md has a normal
# live turn at about 1.0 to 1.4 s. The plan call has 20 s, so it splits 12 s and 8 s.
PRIMARY_SHARE = 0.6


async def once(make_call, pause: float = 0.3):
    """Await make_call(). If it fails with a transient provider error, wait briefly and try once more."""
    try:
        return await make_call()
    except ai.AIError as e:
        if not any(code in str(e) for code in TRANSIENT):
            raise
        log.warning("provider busy, retrying once")
        await asyncio.sleep(pause)
        return await make_call()


def backup_model() -> str:
    """The backup model's name, or "" when there is none (the default)."""
    name = os.getenv(BACKUP_ENV, "").strip().removeprefix("models/")
    primary = (config.GEMINI_MODEL or "").strip().removeprefix("models/")
    return "" if name == primary else name  # a second try on the same model would only spend time


def busy_or_timed_out(error: BaseException) -> bool:
    """A busy provider (the codes in TRANSIENT) or a timeout. Anything else, such as a bad key or bad JSON, is not
    something a second model would fix, so it keeps today's path."""
    return isinstance(error, asyncio.TimeoutError) or (
        isinstance(error, ai.AIError) and any(code in str(error) for code in TRANSIENT))


async def with_backup(call, timeout: float, pause: float = 0.3, label: str = "call"):
    """Run call(model) within `timeout` seconds in total. Returns (result, backup_name).

    call(None) must make the primary model's call exactly as it was written before backups existed. call(name) must
    make the same call on the backup model, for example by passing llm_model=name to ai.generate_text. The primary
    runs through once() and may use PRIMARY_SHARE of the time. If it fails busy or times out, the backup is tried once
    (no retry of its own) in the time that is left. backup_name is None when the primary produced the result.
    When both fail this raises the backup's error, so the caller degrades exactly as it did before."""
    name = backup_model()
    if not name:
        return await asyncio.wait_for(once(lambda: call(None), pause), timeout=timeout), None
    loop = asyncio.get_running_loop()
    start = loop.time()
    try:
        return await asyncio.wait_for(once(lambda: call(None), pause), timeout=timeout * PRIMARY_SHARE), None
    except Exception as primary_error:
        if not busy_or_timed_out(primary_error):
            raise
        log.warning("backup_model trying label=%s model=%s primary_error=%s", label, name, type(primary_error).__name__)
        failure = primary_error
    try:
        result = await asyncio.wait_for(call(name), timeout=max(0.0, timeout - (loop.time() - start)))
    except Exception as backup_error:
        log.warning("backup_model failed label=%s model=%s error=%s", label, name, type(backup_error).__name__)
        raise backup_error from failure
    log.warning("backup_model used label=%s model=%s", label, name)
    return result, name

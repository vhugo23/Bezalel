"""One quick retry when the model provider says it is busy. Used by the plan call, the live reply and the gap check.
Each caller keeps its own overall time limit (asyncio.wait_for around this), so a retry cannot run past it."""
import asyncio
import logging

from app.core import ai

log = logging.getLogger("prepcrew.retry")

TRANSIENT = ("error 503", "error 429", "error 500", "error 502", "error 504")


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

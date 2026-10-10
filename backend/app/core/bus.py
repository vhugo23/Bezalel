"""In-process publish/subscribe, used for Server-Sent Events.

Each channel (for example a session id) keeps a short history so a client that connects late
still receives events that already happened (e.g. grading finished before the page subscribed).
Single-process only: if the app ever runs with several workers, replace this with Postgres LISTEN/NOTIFY.
"""
import asyncio
from collections import defaultdict
from typing import AsyncIterator

HISTORY_LIMIT = 500

_history: dict[str, list[dict]] = defaultdict(list)
_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)


async def publish(channel: str, event: str, data: dict) -> None:
    item = {"event": event, "data": data}
    hist = _history[channel]
    hist.append(item)
    if len(hist) > HISTORY_LIMIT:
        del hist[: len(hist) - HISTORY_LIMIT]
    for q in list(_subscribers[channel]):
        q.put_nowait(item)


async def subscribe(channel: str, replay: bool = True) -> AsyncIterator[dict]:
    q: asyncio.Queue = asyncio.Queue()
    if replay:
        for item in _history[channel]:
            q.put_nowait(item)
    _subscribers[channel].add(q)
    try:
        while True:
            yield await q.get()
    finally:
        _subscribers[channel].discard(q)


def history(channel: str) -> list[dict]:
    return list(_history[channel])


def clear(channel: str) -> None:
    _history.pop(channel, None)

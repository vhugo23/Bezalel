"""Server-Sent Events response built on core.bus."""
import asyncio
import json

from fastapi.responses import StreamingResponse

from app.core import bus

KEEPALIVE_SECONDS = 15


def _format(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def sse_response(channel: str, stop_on: set[str] | None = None) -> StreamingResponse:
    """Streams every event published on `channel` (history first). Closes after an event named in `stop_on`."""
    stop_on = stop_on or set()

    async def stream():
        events = bus.subscribe(channel)
        try:
            while True:
                try:
                    item = await asyncio.wait_for(events.__anext__(), timeout=KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield _format(item["event"], item["data"])
                if item["event"] in stop_on:
                    return
        finally:
            await events.aclose()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

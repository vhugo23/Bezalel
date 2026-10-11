"""PrepCrew WebSockets, all under /ws. Contract: contracts/ws_messages.md.
Every message is JSON with a `type`, except audio, which is binary. Unknown types are logged and ignored."""
import asyncio
import contextlib
import json
import logging
import time
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app import config
from app.core import voice
from app.modules.prepcrew import service

log = logging.getLogger("prepcrew.ws")
router = APIRouter()

_board_clients: dict[str, set[WebSocket]] = defaultdict(set)


async def _send(ws: WebSocket, type_: str, **fields):
    await ws.send_text(json.dumps({"type": type_, **fields}))


async def _error(ws: WebSocket, code: str, message: str, recoverable: bool = True):
    await _send(ws, "error", code=code, message=message, recoverable=recoverable)


async def _open(ws: WebSocket, session_id: str) -> dict | None:
    await ws.accept()
    try:
        return await service.get_session(session_id)
    except service.NotFound:
        await _error(ws, "session_not_found", "session not found", recoverable=False)
        await ws.close(code=4404)
        return None


def _parse(msg: dict) -> tuple[str | None, dict | bytes | None]:
    if msg.get("bytes") is not None:
        return "binary", msg["bytes"]
    text = msg.get("text")
    if text is None:
        return None, None
    try:
        data = json.loads(text)
    except ValueError:
        return "invalid", None
    return (data.get("type") if isinstance(data, dict) else "invalid"), data


class _Conn:
    """Wraps a websocket so the audio task and the main loop never write at the same time."""

    def __init__(self, ws: WebSocket):
        self.ws, self._lock = ws, asyncio.Lock()

    async def send_text(self, text: str):
        async with self._lock:
            await self.ws.send_text(text)

    async def send_bytes(self, data: bytes):
        async with self._lock:
            await self.ws.send_bytes(data)


async def _safe(coro):
    """Sending to a socket that just closed is not an error worth surfacing."""
    try:
        await coro
    except Exception:
        pass


async def _speak(conn: _Conn, session_id: str, text: str, turn: int):
    """Streams the interviewer line as binary audio frames, then tts_done. Never raises: a voice failure
    must not end the interview, the text reply was already sent. Cancelling this task is how barge-in works."""
    start = time.perf_counter()
    first_ms = None
    interrupted = False
    pcm = config.ELEVENLABS_OUTPUT_FORMAT.startswith("pcm_")
    carry = b""  # PCM samples are 2 bytes. Network chunks can split one, and a player needs whole samples.
    try:
        async with asyncio.timeout(config.TASK_TIMEOUT_SECONDS):
            async for chunk in voice.stream(text):
                if pcm:
                    chunk = carry + chunk
                    carry = chunk[-1:] if len(chunk) % 2 else b""
                    chunk = chunk[: len(chunk) - len(carry)]
                    if not chunk:
                        continue
                if first_ms is None:
                    first_ms = (time.perf_counter() - start) * 1000  # request sent to first audio bytes
                    await service.record_timing(session_id, "tts_first_audio", first_ms, turn)
                    await _send(conn, "timing", turn=turn, stage="tts_first_audio", ms=round(first_ms, 1))
                await conn.send_bytes(chunk)
    except asyncio.CancelledError:
        interrupted = True
    except Exception as e:  # provider error, bad key, timeout, closed socket
        log.warning("tts failed: %s", type(e).__name__)
        await _safe(_error(conn, "tts_failed", "voice failed, the text reply is still valid"))
    await _safe(_send(conn, "tts_done", turn=turn, interrupted=interrupted))


@router.websocket("/ws/voice/{session_id}")
async def voice_ws(ws: WebSocket, session_id: str):
    session = await _open(ws, session_id)
    if session is None:
        return
    conn = _Conn(ws)
    d = session["data"]
    await _send(conn, "state", state=d.get("state", "intake"))
    if d.get("last_interviewer_text"):  # reconnect resumes where it left off
        await _send(conn, "interviewer_text", text=d["last_interviewer_text"], turn=d.get("turn", 0))
    tts_task: asyncio.Task | None = None

    async def stop_tts():
        nonlocal tts_task
        if tts_task is not None and not tts_task.done():
            tts_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await tts_task
        tts_task = None

    audio_warned = False
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            kind, data = _parse(msg)
            if kind == "binary":  # 16 kHz mono PCM audio
                # TODO: stream to speech-to-text; send transcript_partial / transcript_final; latency timings.
                if not audio_warned:
                    await _error(conn, "voice_not_implemented", "speech-to-text not implemented yet; use text_answer")
                    audio_warned = True
            elif kind == "start":  # a click in the browser, so audio is allowed to play: speak the opening line
                current = (await service.get_session(session_id))["data"]
                if current.get("last_interviewer_text"):
                    await stop_tts()
                    tts_task = asyncio.create_task(
                        _speak(conn, session_id, current["last_interviewer_text"], current.get("turn", 0)))
            elif kind == "text_answer":
                await stop_tts()  # a new answer cuts off whatever is still playing
                try:
                    r = await service.handle_answer(session_id, str(data.get("text", "")))
                except service.BadRequest as e:
                    await _error(conn, "bad_answer", str(e))
                    continue
                await _send(conn, "transcript_final", text=data.get("text", ""), turn=r["turn"], answer_id=r["answer_id"])
                await _send(conn, "interviewer_text", text=r["next_question"], turn=r["turn"])
                await _send(conn, "timing", turn=r["turn"], stage="turn_total", ms=round(r["turn_total_ms"], 1))
                tts_task = asyncio.create_task(_speak(conn, session_id, r["next_question"], r["turn"]))
            elif kind == "barge_in":
                await stop_tts()  # the cancelled task sends tts_done with interrupted true
            elif kind == "speech_end":
                pass  # TODO: start the latency clock once speech-to-text is wired
            elif kind == "invalid":
                await _error(conn, "bad_message", "messages must be JSON objects with a type")
            else:
                log.info("voice ws: ignoring unknown message type %r", kind)
    except WebSocketDisconnect:
        pass  # the session stays; reconnecting with the same id resumes
    finally:
        if tts_task is not None and not tts_task.done():
            tts_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await tts_task


@router.websocket("/ws/board/{session_id}")
async def board_ws(ws: WebSocket, session_id: str):
    session = await _open(ws, session_id)
    if session is None:
        return
    is_ipad = False
    _board_clients[session_id].add(ws)
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            kind, data = _parse(msg)
            if kind == "pair":
                current = await service.get_session(session_id)
                if str(data.get("code", "")).upper() == current["data"].get("pair_code"):
                    is_ipad = True
                    await _send(ws, "paired", session_id=session_id)
                else:
                    await _error(ws, "bad_pair_code", "pair code does not match")
            elif kind == "probe":
                if is_ipad:
                    await _error(ws, "laptop_only", "probes come from the laptop view")
                    continue
                try:
                    event = await service.record_probe(session_id, data.get("action", "probe_voltage"),
                                                       data.get("node"), data.get("scenario_id"))
                except (service.NotFound, service.BadRequest, service.NotImplementedYet) as e:
                    await _error(ws, "probe_failed", str(e))
                    continue
                for client in list(_board_clients[session_id]):  # laptop and paired iPad both see it
                    try:
                        await _send(client, "probe_result", **event)
                    except Exception:
                        _board_clients[session_id].discard(client)
            elif kind in ("stroke_snapshot", "builder_netlist"):
                # TODO: builder_diff critique (exact) and vision critique (with confidence).
                await _error(ws, "not_implemented", f"{kind} is not implemented yet")
            elif kind == "invalid":
                await _error(ws, "bad_message", "messages must be JSON objects with a type")
            else:
                log.info("board ws: ignoring unknown message type %r", kind)
    except WebSocketDisconnect:
        pass
    finally:
        _board_clients[session_id].discard(ws)

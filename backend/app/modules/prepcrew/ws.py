"""PrepCrew WebSockets, all under /ws. Contract: contracts/ws_messages.md.
Every message is JSON with a `type`, except audio, which is binary. Unknown types are logged and ignored."""
import json
import logging
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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


@router.websocket("/ws/voice/{session_id}")
async def voice_ws(ws: WebSocket, session_id: str):
    session = await _open(ws, session_id)
    if session is None:
        return
    d = session["data"]
    await _send(ws, "state", state=d.get("state", "intake"))
    if d.get("last_interviewer_text"):  # reconnect resumes where it left off
        await _send(ws, "interviewer_text", text=d["last_interviewer_text"], turn=d.get("turn", 0))
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
                    await _error(ws, "voice_not_implemented", "speech-to-text not implemented yet; use text_answer")
                    audio_warned = True
            elif kind == "text_answer":
                try:
                    r = await service.handle_answer(session_id, str(data.get("text", "")))
                except service.BadRequest as e:
                    await _error(ws, "bad_answer", str(e))
                    continue
                await _send(ws, "transcript_final", text=data.get("text", ""), turn=r["turn"], answer_id=r["answer_id"])
                await _send(ws, "interviewer_text", text=r["next_question"], turn=r["turn"])
                await _send(ws, "timing", turn=r["turn"], stage="turn_total", ms=round(r["turn_total_ms"], 1))
                # TODO: stream ElevenLabs audio as binary tts_chunk frames, then tts_done.
                await _send(ws, "tts_done", turn=r["turn"])
            elif kind in ("speech_end", "barge_in"):
                pass  # TODO: start the latency clock / stop TTS once voice is implemented
            elif kind == "invalid":
                await _error(ws, "bad_message", "messages must be JSON objects with a type")
            else:
                log.info("voice ws: ignoring unknown message type %r", kind)
    except WebSocketDisconnect:
        pass  # the session stays; reconnecting with the same id resumes


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

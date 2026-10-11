"""Speech out over /ws/voice: audio frames, timing, barge-in, failures. The voice provider is stubbed,
so no keys or network are needed. One test checks the real ElevenLabs request shape with a mock transport."""
import asyncio
import contextlib
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config
from app.core import voice
from app.main import app
from app.modules.prepcrew import service

client = TestClient(app)


def new_session() -> str:
    plan = client.post("/api/plans", json={"job_posting": "j", "resume": "r", "user_id": "u"}).json()
    return client.post("/api/sessions", json={"plan_id": plan["plan_id"], "user_id": "u", "consent": True}
                       ).json()["session_id"]


def recv(ws):
    """Next message: bytes for an audio frame, a dict for JSON."""
    m = ws.receive()
    return m["bytes"] if m.get("bytes") is not None else json.loads(m["text"])


def recv_until(ws, type_):
    """Collect messages up to and including the first JSON message of this type."""
    got = []
    while True:
        m = recv(ws)
        got.append(m)
        if isinstance(m, dict) and m.get("type") == type_:
            return got


@contextlib.contextmanager
def connect(sid):
    with client.websocket_connect(f"/ws/voice/{sid}") as ws:
        assert recv(ws)["type"] == "state"
        assert recv(ws)["type"] == "interviewer_text"  # the opening question
        yield ws


def stub_voice(monkeypatch, chunks=(b"\x01\x02" * 100, b"\x03\x04" * 100), delay=0.0, error=None, record=None):
    async def stream(text, voice_id=None):
        if record is not None:
            record["texts"].append(text)
        try:
            for c in chunks:
                if delay:
                    await asyncio.sleep(delay)
                yield c
            if error:
                raise error
        finally:
            if record is not None:
                record["closed"] = True
    monkeypatch.setattr(voice, "stream", stream)


def test_audio_frames_arrive_after_the_text_and_before_tts_done(monkeypatch):
    stub_voice(monkeypatch)
    sid = new_session()
    with connect(sid) as ws:
        ws.send_json({"type": "text_answer", "text": "I check the supply first"})
        msgs = recv_until(ws, "tts_done")
    kinds = ["audio" if isinstance(m, bytes) else m["type"] for m in msgs]
    assert kinds[:3] == ["transcript_final", "interviewer_text", "timing"]
    assert kinds.count("audio") == 2
    assert kinds[-1] == "tts_done"
    assert kinds.index("interviewer_text") < kinds.index("audio")  # text shows before audio
    assert msgs[-1]["interrupted"] is False
    stages = [m["stage"] for m in msgs if isinstance(m, dict) and m["type"] == "timing"]
    assert stages == ["turn_total", "tts_first_audio"]


def test_pcm_frames_are_whole_samples(monkeypatch):
    """A network chunk can end mid-sample. The server must not forward half a 16-bit sample."""
    stub_voice(monkeypatch, chunks=(b"", b"", b""))
    sid = new_session()
    with connect(sid) as ws:
        ws.send_json({"type": "text_answer", "text": "hello"})
        msgs = recv_until(ws, "tts_done")
    frames = [m for m in msgs if isinstance(m, bytes)]
    assert frames and all(len(f) % 2 == 0 for f in frames)
    assert b"".join(frames) == bytes(range(1, 9))  # nothing lost or reordered


def test_tts_first_audio_is_measured_and_reported_in_metrics(monkeypatch):
    stub_voice(monkeypatch)
    sid = new_session()
    with connect(sid) as ws:
        ws.send_json({"type": "text_answer", "text": "hello"})
        recv_until(ws, "tts_done")
    m = client.get(f"/api/metrics/{sid}").json()
    assert m["tts_first_audio_ms"] is not None and m["tts_first_audio_ms"] >= 0
    assert m["stt_ms"] is None  # not measured, so not reported


def test_fake_voice_sends_no_audio_and_still_finishes(monkeypatch):
    sid = new_session()  # VOICE_PROVIDER is fake in tests
    with connect(sid) as ws:
        ws.send_json({"type": "text_answer", "text": "hello"})
        msgs = recv_until(ws, "tts_done")
    assert not any(isinstance(m, bytes) for m in msgs)
    assert [m["type"] for m in msgs] == ["transcript_final", "interviewer_text", "timing", "tts_done"]


def test_voice_failure_keeps_the_text_and_the_socket(monkeypatch):
    stub_voice(monkeypatch, chunks=(), error=voice.VoiceError("ElevenLabs error 500"))
    sid = new_session()
    with connect(sid) as ws:
        ws.send_json({"type": "text_answer", "text": "hello"})
        msgs = recv_until(ws, "tts_done")
        types = [m["type"] for m in msgs]
        assert "interviewer_text" in types and "error" in types
        err = next(m for m in msgs if m["type"] == "error")
        assert err["code"] == "tts_failed" and err["recoverable"] is True
        ws.send_json({"type": "text_answer", "text": "second answer"})  # the interview goes on
        assert recv_until(ws, "tts_done")


def test_voice_timeout_is_reported_not_fatal(monkeypatch):
    stub_voice(monkeypatch, chunks=(b"x",) * 1000, delay=0.05)
    monkeypatch.setattr(config, "TASK_TIMEOUT_SECONDS", 0.2)
    sid = new_session()
    with connect(sid) as ws:
        ws.send_json({"type": "text_answer", "text": "hello"})
        msgs = recv_until(ws, "tts_done")
    assert any(isinstance(m, dict) and m.get("code") == "tts_failed" for m in msgs)


def test_barge_in_stops_the_audio(monkeypatch):
    rec = {"texts": [], "closed": False}
    stub_voice(monkeypatch, chunks=(b"a" * 64,) * 200, delay=0.02, record=rec)
    sid = new_session()
    with connect(sid) as ws:
        ws.send_json({"type": "text_answer", "text": "hello"})
        while not isinstance(recv(ws), bytes):  # wait for audio to start
            pass
        ws.send_json({"type": "barge_in", "t_client": 1})
        msgs = recv_until(ws, "tts_done")
        assert msgs[-1]["interrupted"] is True
        assert sum(isinstance(m, bytes) for m in msgs) < 150  # it did not play the whole clip
        assert rec["closed"] is True
        ws.send_json({"type": "text_answer", "text": "next"})  # the socket still works afterwards
        assert recv_until(ws, "transcript_final")


def test_a_new_answer_cuts_off_the_previous_audio(monkeypatch):
    rec = {"texts": [], "closed": False}
    stub_voice(monkeypatch, chunks=(b"a" * 64,) * 200, delay=0.02, record=rec)
    sid = new_session()
    with connect(sid) as ws:
        ws.send_json({"type": "text_answer", "text": "one"})
        while not isinstance(recv(ws), bytes):
            pass
        ws.send_json({"type": "text_answer", "text": "two"})
        msgs = recv_until(ws, "transcript_final")
    done = [m for m in msgs if isinstance(m, dict) and m["type"] == "tts_done"]
    assert done and done[0]["interrupted"] is True
    assert len(rec["texts"]) >= 1


def test_start_speaks_the_opening_question(monkeypatch):
    rec = {"texts": [], "closed": False}
    stub_voice(monkeypatch, record=rec)
    sid = new_session()
    opening = asyncio.run(service.get_session(sid))["data"]["last_interviewer_text"]
    with connect(sid) as ws:
        ws.send_json({"type": "start"})
        msgs = recv_until(ws, "tts_done")
    assert rec["texts"] == [opening]
    assert any(isinstance(m, bytes) for m in msgs)


def test_dropping_the_connection_mid_audio_stops_the_stream(monkeypatch):
    rec = {"texts": [], "closed": False}
    stub_voice(monkeypatch, chunks=(b"a" * 64,) * 500, delay=0.02, record=rec)
    sid = new_session()
    with connect(sid) as ws:
        ws.send_json({"type": "text_answer", "text": "hello"})
        while not isinstance(recv(ws), bytes):
            pass
    deadline = time.time() + 3
    while not rec["closed"] and time.time() < deadline:
        time.sleep(0.05)
    assert rec["closed"] is True  # the audio task was cancelled, not left running


# ---- the real provider's request, against a mock transport ----

def elevenlabs_with(monkeypatch, handler, *, key="test-key", voice_id="voice123", model="eleven_flash_v2_5"):
    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(config, "VOICE_PROVIDER", "elevenlabs")
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", key)
    monkeypatch.setattr(config, "ELEVENLABS_VOICE_ID", voice_id)
    monkeypatch.setattr(config, "ELEVENLABS_MODEL", model)


def test_elevenlabs_request_shape_and_streamed_bytes(monkeypatch):
    seen = {}
    def handler(request: httpx.Request):
        seen.update(url=str(request.url), key=request.headers.get("xi-api-key"), body=json.loads(request.content))
        return httpx.Response(200, content=b"\x00\x01" * 500)
    elevenlabs_with(monkeypatch, handler)
    audio = asyncio.run(voice.speak("What would you measure first?"))
    assert audio == b"\x00\x01" * 500
    assert seen["url"].startswith("https://api.elevenlabs.io/v1/text-to-speech/voice123/stream")
    assert "output_format=pcm_16000" in seen["url"]
    assert seen["key"] == "test-key"
    assert seen["body"] == {"text": "What would you measure first?", "model_id": "eleven_flash_v2_5"}


def test_elevenlabs_errors_do_not_leak_the_key(monkeypatch):
    def handler(request):
        return httpx.Response(401, json={"detail": {"status": "missing_permissions"}})
    elevenlabs_with(monkeypatch, handler, key="sk-super-secret-value")
    with pytest.raises(voice.VoiceError) as e:
        asyncio.run(voice.speak("hello"))
    assert "401" in str(e.value) and "sk-super-secret-value" not in str(e.value)


@pytest.mark.parametrize("field,message", [("ELEVENLABS_API_KEY", "API_KEY"), ("ELEVENLABS_VOICE_ID", "VOICE_ID")])
def test_elevenlabs_missing_settings_are_clear_errors(monkeypatch, field, message):
    elevenlabs_with(monkeypatch, lambda r: httpx.Response(200, content=b"x"))
    monkeypatch.setattr(config, field, "")
    with pytest.raises(voice.VoiceError) as e:
        asyncio.run(voice.speak("hello"))
    assert message in str(e.value)

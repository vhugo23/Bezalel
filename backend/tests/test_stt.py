"""Speech in over /ws/voice (push-to-talk): audio frames are buffered, speech_end transcribes them and runs
the same path as a typed answer. The transcriber is stubbed, so no keys or network are needed."""
import asyncio

import httpx
import pytest

from app import config
from app.core import store, voice
from app.modules.prepcrew import service, ws as ws_module
from tests.test_voice_out import client, connect, new_session, recv, recv_until, stub_voice

ONE_SECOND = b"\x01\x02" * 16000  # 1 s of 16 kHz 16-bit mono


def stub_stt(monkeypatch, text="I would check the supply rail first", error=None, delay=0.0, record=None):
    async def transcribe(pcm):
        if record is not None:
            record.append(pcm)
        if delay:
            await asyncio.sleep(delay)
        if error:
            raise error
        return text
    monkeypatch.setattr(voice, "transcribe", transcribe)


def answers(sid):
    return [e["data"]["text"] for e in asyncio.run(store.list_events(sid, kind="answer"))]


def test_spoken_answer_goes_through_the_same_path_as_a_typed_one(monkeypatch):
    got = []
    stub_stt(monkeypatch, record=got)
    stub_voice(monkeypatch)
    sid = new_session()
    with connect(sid) as ws:
        ws.send_bytes(ONE_SECOND[:20000])
        ws.send_bytes(ONE_SECOND[20000:])
        ws.send_json({"type": "speech_end"})
        msgs = recv_until(ws, "tts_done")
    kinds = ["audio" if isinstance(m, bytes) else m["type"] for m in msgs]
    assert kinds[:4] == ["timing", "transcript_final", "interviewer_text", "timing"]
    assert msgs[0]["stage"] == "stt" and msgs[3]["stage"] == "turn_total"
    assert msgs[1]["text"] == "I would check the supply rail first"
    assert got == [ONE_SECOND]  # frames were joined in order, nothing lost
    assert answers(sid) == ["I would check the supply rail first"]
    assert "audio" in kinds  # the reply is spoken back


def test_stt_time_is_measured_and_reported_in_metrics(monkeypatch):
    from types import SimpleNamespace
    clock=[100.0]
    async def transcribe(_):
        clock[0]+=.125
        return 'I would check the supply rail first'
    monkeypatch.setattr(voice,'transcribe',transcribe)
    monkeypatch.setattr(ws_module,'time',SimpleNamespace(perf_counter=lambda:clock[0]))
    sid = new_session()
    with connect(sid) as ws:
        ws.send_bytes(ONE_SECOND)
        ws.send_json({"type": "speech_end"})
        recv_until(ws, "tts_done")
    m = client.get(f"/api/metrics/{sid}").json()
    assert m["stt_ms"] == pytest.approx(125)


def test_odd_trailing_byte_is_dropped(monkeypatch):
    got = []
    stub_stt(monkeypatch, record=got)
    sid = new_session()
    with connect(sid) as ws:
        ws.send_bytes(ONE_SECOND + b"\x07")
        ws.send_json({"type": "speech_end"})
        recv_until(ws, "tts_done")
    assert len(got[0]) % 2 == 0


def test_speech_end_without_audio(monkeypatch):
    got = []
    stub_stt(monkeypatch, record=got)
    with connect(new_session()) as ws:
        ws.send_json({"type": "speech_end"})
        assert recv(ws)["code"] == "no_audio"
    assert got == []


def test_too_short_is_rejected_before_calling_the_provider(monkeypatch):
    got = []
    stub_stt(monkeypatch, record=got)
    sid = new_session()
    with connect(sid) as ws:
        ws.send_bytes(b"\x01\x02" * 100)  # about 6 ms
        ws.send_json({"type": "speech_end"})
        assert recv(ws)["code"] == "too_short"
    assert got == [] and answers(sid) == []


def test_empty_transcript_stores_no_answer(monkeypatch):
    stub_stt(monkeypatch, text="   ")
    sid = new_session()
    with connect(sid) as ws:
        ws.send_bytes(ONE_SECOND)
        ws.send_json({"type": "speech_end"})
        msgs = [recv(ws), recv(ws)]
    assert [m.get("code") or m["stage"] for m in msgs] == ["stt", "no_speech"]
    assert answers(sid) == []
    assert asyncio.run(service.get_session(sid))["data"]["turn"] == 0


def test_stt_failure_is_recoverable_and_typing_still_works(monkeypatch):
    stub_stt(monkeypatch, error=voice.VoiceError("ElevenLabs speech to text error 500"))
    sid = new_session()
    with connect(sid) as ws:
        ws.send_bytes(ONE_SECOND)
        ws.send_json({"type": "speech_end"})
        err = recv(ws)
        assert err["code"] == "stt_failed" and err["recoverable"] is True
        ws.send_json({"type": "text_answer", "text": "typing instead"})
        assert recv_until(ws, "transcript_final")[-1]["text"] == "typing instead"
    assert answers(sid) == ["typing instead"]


def test_stt_timeout_is_a_recoverable_error(monkeypatch):
    stub_stt(monkeypatch, delay=5)
    monkeypatch.setattr(config, "STT_TIMEOUT_SECONDS", 0.1)
    with connect(new_session()) as ws:
        ws.send_bytes(ONE_SECOND)
        ws.send_json({"type": "speech_end"})
        assert recv(ws)["code"] == "stt_failed"


def test_fake_provider_never_invents_a_transcript():
    sid = new_session()  # VOICE_PROVIDER is fake in tests
    with connect(sid) as ws:
        ws.send_bytes(ONE_SECOND)
        ws.send_json({"type": "speech_end"})
        assert recv(ws)["code"] == "stt_failed"
    assert answers(sid) == []


def test_over_long_recording_is_refused_once_and_not_graded(monkeypatch):
    got = []
    stub_stt(monkeypatch, record=got)
    monkeypatch.setattr(ws_module, "MAX_AUDIO_BYTES", 10000)
    sid = new_session()
    with connect(sid) as ws:
        for _ in range(5):
            ws.send_bytes(b"\x01\x02" * 2000)  # 4000 bytes each, over the cap from the third
        assert recv(ws)["code"] == "audio_too_long"
        ws.send_json({"type": "speech_end"})
        ws.send_bytes(ONE_SECOND[:8000])  # a fresh recording works afterwards
        ws.send_json({"type": "speech_end"})
        msgs = recv_until(ws, "tts_done")
    assert got == [ONE_SECOND[:8000]]  # the over-long one was dropped whole, never transcribed
    assert sum(1 for m in msgs if isinstance(m, dict) and m.get("code") == "audio_too_long") == 0
    assert len(answers(sid)) == 1


def test_barge_in_discards_a_half_finished_recording(monkeypatch):
    got = []
    stub_stt(monkeypatch, record=got)
    with connect(new_session()) as ws:
        ws.send_bytes(b"\x09\x09" * 8000)         # an abandoned press
        ws.send_json({"type": "barge_in"})        # the next press starts clean
        ws.send_bytes(ONE_SECOND)
        ws.send_json({"type": "speech_end"})
        recv_until(ws, "tts_done")
    assert got == [ONE_SECOND]


def test_speech_end_cuts_off_the_interviewer(monkeypatch):
    stub_stt(monkeypatch)
    stub_voice(monkeypatch, chunks=(b"a" * 64,) * 300, delay=0.02)
    with connect(new_session()) as ws:
        ws.send_json({"type": "text_answer", "text": "first"})
        while not isinstance(recv(ws), bytes):
            pass
        ws.send_bytes(ONE_SECOND)
        ws.send_json({"type": "speech_end"})
        msgs = recv_until(ws, "transcript_final")
    done = [m for m in msgs if isinstance(m, dict) and m["type"] == "tts_done"]
    assert done and done[0]["interrupted"] is True


# ---- the real provider's request, against a mock transport ----

def elevenlabs_with(monkeypatch, handler, key="test-key"):
    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(config, "VOICE_PROVIDER", "elevenlabs")
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", key)


def test_elevenlabs_transcribe_request_shape(monkeypatch):
    seen = {}
    def handler(request: httpx.Request):
        seen.update(url=str(request.url), key=request.headers.get("xi-api-key"), body=request.content,
                    ctype=request.headers.get("content-type", ""))
        return httpx.Response(200, json={"text": "  hello there  ", "language_code": "en"})
    elevenlabs_with(monkeypatch, handler)
    assert asyncio.run(voice.transcribe(ONE_SECOND)) == "hello there"
    assert seen["url"] == "https://api.elevenlabs.io/v1/speech-to-text"
    assert seen["key"] == "test-key" and seen["ctype"].startswith("multipart/form-data")
    for part in (b'name="model_id"', b"scribe_v2", b'name="file_format"', b"pcm_s16le_16", b'name="file"'):
        assert part in seen["body"]
    assert ONE_SECOND in seen["body"]


def test_elevenlabs_transcribe_error_does_not_leak_the_key(monkeypatch):
    elevenlabs_with(monkeypatch, lambda r: httpx.Response(401, json={"detail": "missing_permissions"}),
                    key="sk-super-secret-value")
    with pytest.raises(voice.VoiceError) as e:
        asyncio.run(voice.transcribe(ONE_SECOND))
    assert "401" in str(e.value) and "sk-super-secret-value" not in str(e.value)


def test_elevenlabs_transcribe_needs_a_key(monkeypatch):
    elevenlabs_with(monkeypatch, lambda r: httpx.Response(200, json={"text": "x"}), key="")
    with pytest.raises(voice.VoiceError) as e:
        asyncio.run(voice.transcribe(ONE_SECOND))
    assert "API_KEY" in str(e.value)

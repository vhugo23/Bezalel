"""End to end check of speech in: real ElevenLabs speaks a sentence, the audio goes back through the real
/ws/voice route as push-to-talk frames, and the transcript is compared with the sentence.
This is one synthetic voice round trip. It says nothing about accuracy on real or noisy speech.
Run:  backend\\.venv\\Scripts\\python spikes\\e2e_stt.py
Uses in-memory storage, never the database. Costs a few ElevenLabs characters and one transcription."""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")
os.environ.setdefault("VOICE_PROVIDER", "elevenlabs")
os.environ.setdefault("ELEVENLABS_MODEL", "eleven_flash_v2_5")
os.environ.setdefault("ELEVENLABS_OUTPUT_FORMAT", "pcm_16000")  # the transcriber takes 16 kHz PCM

from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.core import voice  # noqa: E402
from app.main import app  # noqa: E402

config.DATABASE_URL = ""
SENTENCE = "I would start by measuring the supply voltage, then check that the ground is connected."


def words(text: str) -> list[str]:
    return "".join(c.lower() if c.isalnum() or c == " " else " " for c in text).split()


def recv(ws):
    m = ws.receive()
    return m["bytes"] if m.get("bytes") is not None else json.loads(m["text"])


def main() -> None:
    pcm = asyncio.run(voice.speak(SENTENCE))
    client = TestClient(app)
    plan = client.post("/api/plans", json={"job_posting": "Hardware intern, PCB debugging", "resume": "Built a PCB",
                                           "user_id": "e2e"}).json()
    sid = client.post("/api/sessions", json={"plan_id": plan["plan_id"], "user_id": "e2e", "consent": True}
                      ).json()["session_id"]
    events, frames_back = [], 0
    with client.websocket_connect(f"/ws/voice/{sid}") as ws:
        recv(ws), recv(ws)
        ws.send_json({"type": "barge_in"})
        for i in range(0, len(pcm), 3200):               # 100 ms frames, like a browser would send
            ws.send_bytes(pcm[i:i + 3200])
        t0 = time.perf_counter()
        ws.send_json({"type": "speech_end"})
        while True:
            m = recv(ws)
            if isinstance(m, bytes):
                frames_back += 1
                continue
            events.append(m)
            if m["type"] in ("tts_done", "error"):
                break
    heard = next((e["text"] for e in events if e["type"] == "transcript_final"), None)
    stt = next((e["ms"] for e in events if e["type"] == "timing" and e["stage"] == "stt"), None)
    reply = next((e["text"] for e in events if e["type"] == "interviewer_text"), None)
    errors = [e for e in events if e["type"] == "error"]
    print(json.dumps({
        "result": "PASS" if heard and not errors else "FAIL",
        "sent": SENTENCE, "heard": heard, "words_match_exactly": heard is not None and words(heard) == words(SENTENCE),
        "audio_seconds_sent": round(len(pcm) / 32000, 2), "stt_ms": stt,
        "speech_end_to_tts_done_ms": round((time.perf_counter() - t0) * 1000, 1),
        "interviewer_reply": reply, "reply_audio_frames": frames_back, "errors": errors,
        "note": "one synthetic sentence round trip"}, indent=2))


if __name__ == "__main__":
    main()

"""End to end check of speech out: real /ws/voice route, real ElevenLabs, LLM provider from backend/.env.
Sends one typed answer, collects the audio frames and timings, and writes a WAV file to listen to.
Run with the backend's python:  backend\\.venv\\Scripts\\python spikes\\e2e_voice_out.py
Uses in-memory storage, never the database. Costs a few ElevenLabs characters per run. Keys are read from backend/.env and never printed."""
import json
import os
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")
os.environ.setdefault("VOICE_PROVIDER", "elevenlabs")  # a value already in the environment wins
os.environ.setdefault("ELEVENLABS_MODEL", "eleven_flash_v2_5")

from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.main import app  # noqa: E402

config.DATABASE_URL = ""  # in-memory storage only: this script must never write to the real database
OUT = Path(__file__).parent / "e2e_voice_out.wav"


def recv(ws):
    m = ws.receive()
    return m["bytes"] if m.get("bytes") is not None else json.loads(m["text"])


def main() -> None:
    client = TestClient(app)
    plan = client.post("/api/plans", json={
        "job_posting": "Embedded hardware intern: PCB debugging, oscilloscope, UART, SPI.",
        "resume": "Built a 3-axis motor controller PCB. Debugged a brownout on the 5V rail with a scope.",
        "user_id": "e2e"}).json()
    s = client.post("/api/sessions", json={"plan_id": plan["plan_id"], "user_id": "e2e", "consent": True}).json()
    sid = s["session_id"]
    answer = "I started by putting the scope on the 5 volt rail to see if it was dipping under load."
    frames, events = [], []
    t_send = None
    with client.websocket_connect(f"/ws/voice/{sid}") as ws:
        events.append(recv(ws))   # state
        events.append(recv(ws))   # opening question text
        ws.send_json({"type": "text_answer", "text": answer})
        t_send = time.perf_counter()
        t_first_frame = None
        while True:
            m = recv(ws)
            if isinstance(m, bytes):
                if t_first_frame is None:
                    t_first_frame = (time.perf_counter() - t_send) * 1000
                frames.append(m)
                continue
            events.append(m)
            if m["type"] == "tts_done":
                break
    total_ms = (time.perf_counter() - t_send) * 1000
    pcm = b"".join(frames)
    if pcm:
        with wave.open(str(OUT), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(int(config.ELEVENLABS_OUTPUT_FORMAT.split("_")[1]))
            w.writeframes(pcm)
    text = next(e["text"] for e in events if e["type"] == "interviewer_text" and e.get("turn") == 1)
    timings = {(e["stage"]): e["ms"] for e in events if e["type"] == "timing"}
    errors = [e for e in events if e["type"] == "error"]
    print(json.dumps({
        "result": "PASS" if pcm and not errors else "FAIL",
        "llm_provider": config.LLM_PROVIDER, "voice_provider": config.VOICE_PROVIDER,
        "plan_degraded": plan["degraded"], "interviewer_said": text,
        "audio_frames": len(frames), "audio_bytes": len(pcm), "all_frames_even": all(len(f) % 2 == 0 for f in frames),
        "audio_seconds": round(len(pcm) / 2 / int(config.ELEVENLABS_OUTPUT_FORMAT.split("_")[1]), 2),
        "timings_ms": timings, "answer_sent_to_first_audio_frame_ms": round(t_first_frame, 1) if frames else None,
        "answer_sent_to_tts_done_ms": round(total_ms, 1),
        "errors": errors, "wav": str(OUT) if pcm else None}, indent=2))


if __name__ == "__main__":
    main()

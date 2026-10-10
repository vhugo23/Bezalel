"""Spike: ElevenLabs speech to text (scribe_v2, upload endpoint).
Feeds back the clip from spike_tts.py, so no microphone is needed. Measures upload-to-transcript time, 3 runs.
This tests the batch endpoint only. The docs page we read did not mention a realtime websocket.
Run spike_tts.py first, then:  python spikes/spike_stt.py"""
import time
from pathlib import Path

import httpx

from _common import key, report
from spike_tts import TEXT

API = "https://api.elevenlabs.io/v1/speech-to-text"
CLIP = Path(__file__).parent / "tts_sample.pcm"


def norm(s: str) -> list[str]:
    return "".join(c.lower() if c.isalnum() or c == " " else " " for c in s).split()


def main() -> None:
    if not CLIP.exists():
        report("stt", "FAIL", reason="run spike_tts.py first, tts_sample.pcm not found")
        return
    audio = CLIP.read_bytes()
    headers = {"xi-api-key": key("ELEVENLABS_API_KEY")}
    times, texts = [], []
    for i in range(3):
        t0 = time.perf_counter()
        try:
            r = httpx.post(
                API, headers=headers,
                data={"model_id": "scribe_v2", "file_format": "pcm_s16le_16", "language_code": "en"},
                files={"file": ("clip.pcm", audio, "application/octet-stream")}, timeout=60,
            )
        except Exception as e:
            report("stt", "FAIL", run=i, error=f"{type(e).__name__}: {e}")
            return
        times.append(round((time.perf_counter() - t0) * 1000, 1))
        if r.status_code != 200:
            report("stt", "FAIL", status=r.status_code, body=r.text[:300])
            return
        texts.append(r.json().get("text", ""))
    ref = norm(TEXT)
    same = [norm(t) == ref for t in texts]
    report("stt", "PASS" if all(texts) else "FAIL", transcribe_ms=times, transcripts=texts,
           exact_word_match=same, audio_bytes=len(audio),
           note="one synthetic sentence round trip, says nothing about accuracy on real speech")


if __name__ == "__main__":
    main()

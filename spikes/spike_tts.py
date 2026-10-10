"""Spike: ElevenLabs streaming TTS. Measures request-sent to first audio bytes, 3 runs.
Also saves a 16 kHz PCM clip that spike_stt.py feeds back in.
Run:  python spikes/spike_tts.py"""
import os
import time
from pathlib import Path

import httpx

from _common import key, report

API = "https://api.elevenlabs.io/v1"
TEXT = "Okay, you said the LED stays dark. What would you measure first?"
OUT = Path(__file__).parent / "tts_sample.pcm"


def pick_voice(headers) -> str:
    vid = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    if vid:
        return vid
    r = httpx.get(f"{API}/voices", headers=headers, timeout=20)
    r.raise_for_status()
    voices = r.json().get("voices", [])
    if not voices:
        raise RuntimeError("no voices available to this key")
    print(f"ELEVENLABS_VOICE_ID empty, using first listed voice: {voices[0].get('name')} ({voices[0]['voice_id']})")
    return voices[0]["voice_id"]


def main() -> None:
    headers = {"xi-api-key": key("ELEVENLABS_API_KEY"), "Content-Type": "application/json"}
    try:
        voice = pick_voice(headers)
    except Exception as e:
        report("tts", "FAIL", stage="voice", error=f"{type(e).__name__}: {e}")
        return
    first_audio_ms, totals_ms, sizes = [], [], []
    for i in range(3):
        t0 = time.perf_counter()
        first = None
        n = 0
        buf = bytearray()
        try:
            with httpx.stream(
                "POST", f"{API}/text-to-speech/{voice}/stream",
                params={"output_format": "pcm_16000"}, headers=headers,
                json={"text": TEXT}, timeout=30,
            ) as r:
                if r.status_code != 200:
                    report("tts", "FAIL", status=r.status_code, body=r.read().decode(errors="replace")[:300])
                    return
                for chunk in r.iter_bytes():
                    if chunk and first is None:
                        first = (time.perf_counter() - t0) * 1000
                    n += len(chunk)
                    buf += chunk
        except Exception as e:
            report("tts", "FAIL", run=i, error=f"{type(e).__name__}: {e}")
            return
        first_audio_ms.append(round(first, 1) if first else None)
        totals_ms.append(round((time.perf_counter() - t0) * 1000, 1))
        sizes.append(n)
        if i == 0:
            OUT.write_bytes(bytes(buf))
    report("tts", "PASS" if all(first_audio_ms) else "FAIL",
           first_audio_ms=first_audio_ms, total_ms=totals_ms, bytes=sizes,
           format="pcm_16000", note="model_id not set, ElevenLabs default used")


if __name__ == "__main__":
    main()

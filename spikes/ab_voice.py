"""Write the same interviewer lines at three ElevenLabs voice settings to WAV files, so a person can listen and choose.
Run:  backend\\.venv\\Scripts\\python spikes\\ab_voice.py
Output: spikes/_runs/voice_ab/<line>_<preset>.wav  (play them in any player).
The presets are starting guesses, not tuned values, and a model may ignore a setting it does not support.
Nothing here claims a preset sounds better. That is the listener's call.
Costs about 750 ElevenLabs characters per run. Keys are read from backend/.env and never printed."""
import asyncio
import os
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")
os.environ.setdefault("VOICE_PROVIDER", "elevenlabs")
os.environ.setdefault("ELEVENLABS_MODEL", "eleven_flash_v2_5")
os.environ.setdefault("ELEVENLABS_OUTPUT_FORMAT", "pcm_16000")

from app import config  # noqa: E402
from app.core import voice  # noqa: E402

LINES = {
    "short": "Which brownout threshold did you hit?",
    "react": "Mostly? What was left?",
    "handoff": "Okay, that covers the project side. Now I've got a circuit that isn't working, and I want to hear how you'd debug it.",
    "question": "If you had to redesign the buck converter section today, what would you change?",
}
PRESETS = {
    "a_default": {},
    "b_looser": {"stability": 0.35, "similarity": 0.75, "style": 0.3, "speed": 1.0},
    "c_brisk": {"stability": 0.5, "speed": 1.08},
}


async def main() -> None:
    out = Path(__file__).parent / "_runs" / "voice_ab"
    out.mkdir(parents=True, exist_ok=True)
    rate = int(config.ELEVENLABS_OUTPUT_FORMAT.split("_")[1])
    for preset, vals in PRESETS.items():
        config.ELEVENLABS_STABILITY = vals.get("stability")
        config.ELEVENLABS_SIMILARITY = vals.get("similarity")
        config.ELEVENLABS_STYLE = vals.get("style")
        config.ELEVENLABS_SPEED = vals.get("speed")
        for name, text in LINES.items():
            try:
                pcm = await voice.speak(text)
            except voice.VoiceError as e:
                print(f"FAIL {preset}/{name}: {e}")
                continue
            path = out / f"{name}_{preset}.wav"
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes(pcm)
            print(f"ok   {path.name}  {len(pcm) / 2 / rate:.1f}s")
    print(f"\nModel: {config.ELEVENLABS_MODEL}. Presets: {PRESETS}")


if __name__ == "__main__":
    asyncio.run(main())

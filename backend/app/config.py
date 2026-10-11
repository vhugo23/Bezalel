import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Resolve from the repository, independent of where uvicorn was started.
load_dotenv(Path(__file__).resolve().parents[2] / '.env')

DATABASE_URL = os.getenv("DATABASE_URL", "")
# Postgres schema the app's tables live in (create it with `python init_db.py`). The app searches this schema first,
# then public (where the timescaledb functions live). Blank = public, as before. Letters, digits and _ only.
DATABASE_SCHEMA = os.getenv("DATABASE_SCHEMA", "").strip()
V2_DATABASE_SCHEMA = os.getenv('V2_DATABASE_SCHEMA', 'prepcrew').strip()
if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', V2_DATABASE_SCHEMA):
    raise ValueError('V2_DATABASE_SCHEMA must be a lowercase PostgreSQL identifier')

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Copy a current model name from Google AI Studio / ai.google.dev. No default on purpose.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
BACKBOARD_API_KEY = os.getenv("BACKBOARD_API_KEY", "")
BACKBOARD_BASE_URL = os.getenv("BACKBOARD_BASE_URL", "https://app.backboard.io/api")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "fake")
VOICE_PROVIDER = os.getenv("VOICE_PROVIDER", "fake")
MEMORY_BACKEND = os.getenv("MEMORY_BACKEND", "")

TASK_TIMEOUT_SECONDS = float(os.getenv("TASK_TIMEOUT_SECONDS", "20"))
# ---- Live interviewer and evaluators (contracts/env.additions.md)
INTERVIEWER_MODEL = os.getenv("INTERVIEWER_MODEL", "")
WHITEBOARD_MODEL = os.getenv("WHITEBOARD_MODEL", "")
# Blank = same provider as LLM_PROVIDER. EVALUATOR_MODEL blank = GEMINI_MODEL.
EVALUATOR_PROVIDER = os.getenv("EVALUATOR_PROVIDER", "")
EVALUATOR_MODEL = os.getenv("EVALUATOR_MODEL", "")
EVALUATOR_CONCURRENCY = int(os.getenv("EVALUATOR_CONCURRENCY", "4"))
EVALUATOR_TIMEOUT_SECONDS = float(os.getenv("EVALUATOR_TIMEOUT_SECONDS", "60"))
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
# Model id sent with each TTS request. Blank uses ElevenLabs' default. eleven_flash_v2_5 had the lowest
# first-audio times in spikes/RESULTS.md (tried by name, not confirmed from docs).
ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "")
# pcm_16000 = 16-bit mono little-endian at 16 kHz. This is what the browser player must expect.
ELEVENLABS_OUTPUT_FORMAT = os.getenv("ELEVENLABS_OUTPUT_FORMAT", "pcm_16000")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")

# ---- Frontend integration
# React dev servers (Vite 5173, CRA/Next 3000). Comma separated. Add the deployed frontend URL later.
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000").split(",") if o.strip()]

# Live interview turns need a short limit, the voice loop sits silent while it waits.
# TASK_TIMEOUT_SECONDS is for background work.
LIVE_TURN_TIMEOUT_SECONDS = float(os.getenv("LIVE_TURN_TIMEOUT_SECONDS", "5"))

# Speech to text (ElevenLabs, upload endpoint). Input audio must be 16 kHz mono 16-bit PCM.
ELEVENLABS_STT_MODEL = os.getenv("ELEVENLABS_STT_MODEL", "scribe_v2")
STT_TIMEOUT_SECONDS = float(os.getenv("STT_TIMEOUT_SECONDS", "15"))

# ElevenLabs voice settings. Blank means "send nothing, use the voice's own settings". Tune by ear with
# spikes/ab_voice.py. Not every model honors every setting (checked per model, not assumed).
def _optional_float(name: str):
    raw = os.getenv(name, "").strip()
    return float(raw) if raw else None


ELEVENLABS_STABILITY = _optional_float("ELEVENLABS_STABILITY")
ELEVENLABS_SIMILARITY = _optional_float("ELEVENLABS_SIMILARITY")
ELEVENLABS_STYLE = _optional_float("ELEVENLABS_STYLE")
ELEVENLABS_SPEED = _optional_float("ELEVENLABS_SPEED")

# Fail threshold ("patience meter", see meter.py). Starting values chosen by hand, not validated.
# One missed REQUIRED skill (0.6) already starts the wrap-up; two end the interview. A missed PREFERRED skill is small.
FAIL_THRESHOLD = float(os.getenv("FAIL_THRESHOLD", "1.0"))
WRAP_UP_AT = float(os.getenv("WRAP_UP_AT", "0.5"))
PENALTY_REQUIRED_UNKNOWN = float(os.getenv("PENALTY_REQUIRED_UNKNOWN", "0.6"))
PENALTY_REQUIRED_PARTIAL = float(os.getenv("PENALTY_REQUIRED_PARTIAL", "0.25"))
PENALTY_PREFERRED_UNKNOWN = float(os.getenv("PENALTY_PREFERRED_UNKNOWN", "0.15"))
PENALTY_PREFERRED_PARTIAL = float(os.getenv("PENALTY_PREFERRED_PARTIAL", "0.05"))
ASSESSOR_TIMEOUT_SECONDS = float(os.getenv("ASSESSOR_TIMEOUT_SECONDS", "4"))
# One answer can add at most this much to the meter, so no single sentence (or one speech-to-text slip) ends an interview.
MAX_PENALTY_PER_ANSWER = float(os.getenv("MAX_PENALTY_PER_ANSWER", "0.6"))
# An answer that ignores the interviewer's question. Counts every time (a new question each time), unlike a skill.
# 0.35 means the second one starts the wrap-up and the third ends a strict interview. Hand-picked, not validated.
PENALTY_NON_ANSWER = float(os.getenv("PENALTY_NON_ANSWER", "0.35"))

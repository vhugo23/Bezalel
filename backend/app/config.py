import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Copy a current model name from Google AI Studio / ai.google.dev. No default on purpose.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
BACKBOARD_API_KEY = os.getenv("BACKBOARD_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
# Set to a model your OpenAI account can use (see OpenAI's models page). No default on purpose.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "fake")
VOICE_PROVIDER = os.getenv("VOICE_PROVIDER", "fake")
MEMORY_BACKEND = os.getenv("MEMORY_BACKEND", "")

ENABLED_MODULES = [m.strip() for m in os.getenv("ENABLED_MODULES", "prepcrew").split(",") if m.strip()]
APP_API_KEY = os.getenv("APP_API_KEY", "")
TASK_TIMEOUT_SECONDS = float(os.getenv("TASK_TIMEOUT_SECONDS", "20"))
# ---- Live interviewer and evaluators (contracts/env.additions.md)
INTERVIEWER_MODEL = os.getenv("INTERVIEWER_MODEL", "")
EVALUATOR_PROVIDER = os.getenv("EVALUATOR_PROVIDER", "fake")
EVALUATOR_MODEL = os.getenv("EVALUATOR_MODEL", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
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
# The React app owns every page. Leave false so the backend serves JSON only (no HTML pages, no /static).
SERVE_HTML = os.getenv("SERVE_HTML", "false").strip().lower() in ("1", "true", "yes")

# Live interview turns need a short limit, the voice loop sits silent while it waits.
# TASK_TIMEOUT_SECONDS is for background work.
LIVE_TURN_TIMEOUT_SECONDS = float(os.getenv("LIVE_TURN_TIMEOUT_SECONDS", "5"))

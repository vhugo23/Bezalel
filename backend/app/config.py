import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
BACKBOARD_API_KEY = os.getenv("BACKBOARD_API_KEY", "")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "fake")
VOICE_PROVIDER = os.getenv("VOICE_PROVIDER", "fake")
MEMORY_BACKEND = os.getenv("MEMORY_BACKEND", "")

ENABLED_MODULES = [m.strip() for m in os.getenv("ENABLED_MODULES", "prepcrew").split(",") if m.strip()]
APP_API_KEY = os.getenv("APP_API_KEY", "")
TASK_TIMEOUT_SECONDS = float(os.getenv("TASK_TIMEOUT_SECONDS", "20"))

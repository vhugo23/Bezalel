"""Core endpoints. Only /api/health: every app endpoint lives in the prepcrew module (contracts/api.md)."""
from fastapi import APIRouter

from app import config

router = APIRouter(prefix="/api", tags=["core"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "database": bool(config.DATABASE_URL),
        "llm_provider": config.LLM_PROVIDER,
        "voice_provider": config.VOICE_PROVIDER,
    }

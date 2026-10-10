"""Idea-agnostic endpoints. The frontend can prototype any idea against these before a module exists."""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app import config
from app.core import ai, store

router = APIRouter(prefix="/api", tags=["core"])


def require_key(x_api_key: str | None = Header(default=None)):
    """If APP_API_KEY is set, the AI endpoints require it. Prevents strangers burning your AI credits."""
    if config.APP_API_KEY and x_api_key != config.APP_API_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing x-api-key")


class RecordIn(BaseModel):
    data: dict
    owner_id: str | None = None


class EventIn(BaseModel):
    subject_id: str
    kind: str
    value: float | None = None
    data: dict = {}


class AIIn(BaseModel):
    prompt: str
    system: str | None = None


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "database": bool(config.DATABASE_URL),
        "llm_provider": config.LLM_PROVIDER,
        "voice_provider": config.VOICE_PROVIDER,
        "modules": config.ENABLED_MODULES,
    }


@router.post("/records/{kind}")
async def create_record(kind: str, body: RecordIn):
    return await store.create_record(kind, body.data, body.owner_id)


@router.get("/records/{kind}")
async def list_records(kind: str, owner_id: str | None = None, limit: int = 50):
    return await store.list_records(kind, owner_id, limit)


@router.get("/record/{record_id}")
async def get_record(record_id: str):
    rec = await store.get_record(record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="record not found")
    return rec


@router.patch("/record/{record_id}")
async def update_record(record_id: str, body: RecordIn):
    rec = await store.update_record(record_id, body.data)
    if rec is None:
        raise HTTPException(status_code=404, detail="record not found")
    return rec


@router.post("/events")
async def add_event(body: EventIn):
    return await store.add_event(body.subject_id, body.kind, body.value, body.data)


@router.get("/events/{subject_id}")
async def list_events(subject_id: str, kind: str | None = None, limit: int = 200):
    return await store.list_events(subject_id, kind, limit)


@router.post("/ai/text", dependencies=[Depends(require_key)])
async def ai_text(body: AIIn):
    return {"text": await ai.generate_text(body.prompt, body.system)}


@router.post("/ai/json", dependencies=[Depends(require_key)])
async def ai_json(body: AIIn):
    try:
        return await ai.generate_json(body.prompt, system=body.system)
    except ai.AIError as e:
        raise HTTPException(status_code=502, detail=str(e))

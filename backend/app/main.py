"""Backend entry point.

URL namespaces (this is what keeps the backend from clashing with the React frontend):
  /api/*            HTTP JSON endpoints
  /ws/*             WebSocket endpoints
  /docs, /openapi.json   generated API docs and schema
Everything else belongs to the frontend. The backend serves no pages and no static files.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from contextlib import asynccontextmanager, suppress

from app import config
from app.core.routes import router as core_router
from app.modules import prepcrew

@asynccontextmanager
async def lifespan(app):
    from app.v2 import assessment, jobs, memory, db
    tasks=[asyncio.create_task(worker()) for worker in (assessment.worker,jobs.worker,memory.worker)] if config.DATABASE_URL else []
    try:yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):await task
        if db._pool:
            await db._pool.close()
            db._pool=None

app = FastAPI(title="PrepCrew backend",lifespan=lifespan)
from app.v2.auth import router as auth_router, AccessBoundary
app.add_middleware(AccessBoundary)

if config.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=['X-PrepCrew-Speech-Fallback'],
    )

app.include_router(core_router)
prepcrew.register(app)

from app.v2.routes import router as v2_router, ws_router as v2_ws_router
app.include_router(v2_router)
app.include_router(v2_ws_router)
app.include_router(auth_router)

_route_openapi = app.openapi


def _openapi_with_legacy_strokes():
    # Fixed-board strokes are no longer an endpoint body, but old sessions, the demo board and the
    # circuit stamp library still use them; keep their schema in the generated client.
    from app.v2.models import Stroke
    schema = _route_openapi()
    stroke = Stroke.model_json_schema(ref_template="#/components/schemas/{model}")
    for name, definition in {**stroke.pop("$defs", {}), "Stroke": stroke}.items():
        schema["components"]["schemas"].setdefault(name, definition)
    return schema


app.openapi = _openapi_with_legacy_strokes


@app.get("/", include_in_schema=False)
async def index():
    return {"service": "api", "docs": "/docs", "health": "/api/health", "openapi": "/openapi.json"}

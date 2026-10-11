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

if config.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(core_router)
prepcrew.register(app)

from app.v2.routes import router as v2_router, ws_router as v2_ws_router
app.include_router(v2_router)
app.include_router(v2_ws_router)


@app.get("/", include_in_schema=False)
async def index():
    return {"service": "api", "docs": "/docs", "health": "/api/health", "openapi": "/openapi.json"}

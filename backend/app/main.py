"""Backend entry point.

URL namespaces (this is what keeps the backend from clashing with the React frontend):
  /api/*            HTTP JSON endpoints
  /ws/*             WebSocket endpoints
  /docs, /openapi.json   generated API docs and schema
Everything else belongs to the frontend. The backend serves no pages and no static files.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.core.routes import router as core_router
from app.modules import prepcrew

app = FastAPI(title="PrepCrew backend")

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


@app.get("/", include_in_schema=False)
async def index():
    return {"service": "api", "docs": "/docs", "health": "/api/health", "openapi": "/openapi.json"}

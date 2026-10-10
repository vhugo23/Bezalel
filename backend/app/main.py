"""Backend entry point.

URL namespaces (this is what keeps the backend from clashing with the React frontend):
  /api/*            HTTP JSON endpoints (core + enabled modules)
  /ws/*             WebSocket endpoints
  /docs, /openapi.json   generated API docs and schema
Everything else belongs to the frontend. With SERVE_HTML=false (the default) the backend serves no pages
and no /static files.
"""
import importlib
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.core.routes import router as core_router

BASE_DIR = Path(__file__).resolve().parent.parent

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

templates = None
if config.SERVE_HTML:
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates

    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Each enabled idea lives in app/modules/<name>/ and exposes register(app, templates)
for name in config.ENABLED_MODULES:
    importlib.import_module(f"app.modules.{name}").register(app, templates)


@app.get("/", include_in_schema=False)
async def index(request: Request):
    if templates is not None:
        return templates.TemplateResponse(request, "index.html")
    return {"service": "api", "docs": "/docs", "health": "/api/health", "openapi": "/openapi.json"}

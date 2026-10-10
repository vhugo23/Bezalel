import importlib
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import config
from app.core.routes import router as core_router

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Hackathon backend")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app.include_router(core_router)

# Each enabled idea lives in app/modules/<name>/ and exposes register(app, templates)
for name in config.ENABLED_MODULES:
    importlib.import_module(f"app.modules.{name}").register(app, templates)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")

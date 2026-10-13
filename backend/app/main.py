"""Backend entry point.

URL namespaces (this is what keeps the backend from clashing with the React frontend):
  /api/*            HTTP JSON endpoints
  /ws/*             WebSocket endpoints
  /docs, /openapi.json   generated API docs and schema
The packaged app also serves the built frontend and its static assets.
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
    workers = [assessment.worker, jobs.worker]
    if memory.enabled():
        workers.append(memory.worker)
    tasks=[asyncio.create_task(worker()) for worker in workers] if config.DATABASE_URL else []
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
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    if request.url.path.startswith('/api/v2/providers'):
        # Pydantic's model-level errors otherwise echo the entire credential body.
        return JSONResponse(status_code=422,content={'detail':[
            {key:item[key] for key in ('type','loc','msg') if key in item}
            for item in error.errors()]})
    return await request_validation_exception_handler(request,error)
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
from app.v2.providers import router as providers_router
app.include_router(providers_router)
from app.v2.speech_connections import router as speech_connections_router
app.include_router(speech_connections_router)

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
    import os
    from pathlib import Path
    from fastapi.responses import FileResponse
    if os.getenv('PREPCREW_WEB_DIST'):
        return FileResponse(Path(os.environ['PREPCREW_WEB_DIST'])/'index.html')
    return {"service": "api", "docs": "/docs", "health": "/api/health", "openapi": "/openapi.json"}


# Built React pages, API and voice sockets share one origin in the packaged app.
import os
if os.getenv('PREPCREW_WEB_DIST'):
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    from starlette.exceptions import HTTPException as StarletteHTTPException
    class WorkspaceFiles(StaticFiles):
        async def get_response(self,path,scope):
            if any(part.startswith('.') for part in Path(path).parts):
                raise StarletteHTTPException(404)
            if path.split('/')[0] in {'api','ws','docs','openapi.json'}:
                raise StarletteHTTPException(404)
            try:return await super().get_response(path,scope)
            except StarletteHTTPException as error:
                if error.status_code!=404 or Path(path).suffix:raise
                return await super().get_response('index.html',scope)
    app.mount('/',WorkspaceFiles(directory=os.environ['PREPCREW_WEB_DIST'],html=True),name='workspace')

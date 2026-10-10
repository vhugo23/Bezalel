"""PrepCrew idea module. To start a different idea, copy this folder to app/modules/<newname>,
edit routes/templates, and set ENABLED_MODULES=<newname> in .env. The core stays untouched."""
from fastapi import Request

from app.modules.prepcrew.routes import router


def register(app, templates):
    app.include_router(router)

    @app.get("/plan")
    async def plan_page(request: Request):
        return templates.TemplateResponse(request, "prepcrew/plan.html")

    @app.get("/session/{session_id}")
    async def session_page(request: Request, session_id: str):
        return templates.TemplateResponse(request, "prepcrew/session.html")

    @app.get("/report/{session_id}")
    async def report_page(request: Request, session_id: str):
        return templates.TemplateResponse(request, "prepcrew/report.html")

    @app.get("/lesson/{topic}")
    async def lesson_page(request: Request, topic: str):
        return templates.TemplateResponse(request, "prepcrew/lesson.html")

    @app.get("/season")
    async def season_page(request: Request):
        return templates.TemplateResponse(request, "prepcrew/season.html")

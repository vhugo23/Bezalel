"""PrepCrew idea module. To start a different idea, copy this folder to app/modules/<newname>,
edit its routes, and set ENABLED_MODULES=<newname> in .env. The core stays untouched.

Routes added: /api/... (routes.py) and /ws/... (ws.py). No page routes unless SERVE_HTML=true,
so the React frontend owns every other path."""
from fastapi import Request

from app.modules.prepcrew import routes, ws


def register(app, templates):
    app.include_router(routes.router)
    app.include_router(ws.router)
    if templates is None:  # API-only mode (default): the frontend owns all page routes
        return

    # Optional blank HTML fallback pages, only when SERVE_HTML=true
    pages = {"/plan": "plan.html", "/session/{session_id}": "session.html",
             "/report/{session_id}": "report.html", "/lesson/{skill_id}": "lesson.html"}
    for path, tpl in pages.items():
        def make(tpl=tpl):
            async def page(request: Request):
                return templates.TemplateResponse(request, f"prepcrew/{tpl}")
            return page
        app.add_api_route(path, make(), methods=["GET"], include_in_schema=False)

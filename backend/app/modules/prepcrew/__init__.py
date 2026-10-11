"""PrepCrew module: HTTP routes under /api (routes.py) and WebSockets under /ws (ws.py).
The React frontend owns every other path."""
from app.modules.prepcrew import routes, ws


def register(app):
    app.include_router(routes.router)
    app.include_router(ws.router)

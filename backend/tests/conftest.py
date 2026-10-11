import pytest

from app import config
from app.core import bus, store


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    """Tests never touch your real database or AI keys, even if .env has them, and start with empty storage."""
    monkeypatch.setattr(config, "DATABASE_URL", "")
    monkeypatch.setattr(config, "MEMORY_BACKEND", "")
    monkeypatch.setattr(config, "BACKBOARD_API_KEY", "")  # never call the real Backboard from tests
    monkeypatch.setattr(config, "LLM_PROVIDER", "fake")
    store._records.clear()
    store._events.clear()
    bus._history.clear()
    yield

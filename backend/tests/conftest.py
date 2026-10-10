import pytest

from app import config


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    """Tests never touch your real database, even if .env has DATABASE_URL."""
    monkeypatch.setattr(config, "DATABASE_URL", "")
    monkeypatch.setattr(config, "MEMORY_BACKEND", "")
    monkeypatch.setattr(config, "LLM_PROVIDER", "fake")
    monkeypatch.setattr(config, "APP_API_KEY", "")

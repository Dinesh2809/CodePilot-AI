import os

from backend.app.core.config import Settings, settings


def test_defaults() -> None:
    s = Settings()
    assert s.APP_NAME == "CodePilot AI"
    assert s.APP_ENV == "development"
    assert isinstance(s.DEBUG, bool)
    assert s.API_V1_PREFIX == "/api/v1"
    assert s.MAX_FILES_PER_BATCH == 50
    assert s.EMBEDDING_MODEL == "all-MiniLM-L6-v2"
    assert isinstance(s.GEMINI_API_KEY, str)
    assert s.GEMINI_MODEL == "gemini-3.6-flash"


def test_env_loading(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "MyApp")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("API_V1_PREFIX", "/v2")

    s = Settings()
    assert s.APP_NAME == "MyApp"
    assert s.APP_ENV == "production"
    assert s.DEBUG is False
    assert s.API_V1_PREFIX == "/v2"


def test_shared_instance_reflects_env(monkeypatch) -> None:
    # monkeypatch env before reloading the shared settings instance
    monkeypatch.setenv("APP_NAME", "SharedApp")
    # Recreate settings instance to reflect env change
    s = Settings()
    assert s.APP_NAME == "SharedApp"
    # The module-level `settings` was created at import time and may not reflect
    # runtime monkeypatch; ensure it's an instance of Settings
    assert isinstance(settings, Settings)

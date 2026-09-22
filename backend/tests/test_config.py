import os

from backend.app.core.config import Settings, settings


def test_defaults() -> None:
    s = Settings()
    assert s.APP_NAME == "CodePilot AI"
    assert s.APP_ENV == "development"
    assert isinstance(s.DEBUG, bool)
    assert s.API_V1_PREFIX == "/api/v1"
    assert s.MAX_FILES_PER_BATCH == 50
    assert s.MAX_TOTAL_UPLOAD_SIZE_MB == 25
    assert s.EMBEDDING_MODEL == "all-MiniLM-L6-v2"
    assert s.EMBEDDING_BATCH_SIZE == 1
    assert s.EMBEDDING_PERSIST_GROUP_SIZE == 8
    assert isinstance(s.GEMINI_API_KEY, str)
    assert s.GEMINI_MODEL == "gemini-3.6-flash"


def test_env_loading(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "MyApp")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("API_V1_PREFIX", "/v2")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:test_password@localhost:5433/codepilot",
    )
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv(
        "CORS_ORIGINS", '["https://codepilot-ai-1-pjss.onrender.com"]'
    )

    s = Settings()
    assert s.APP_NAME == "MyApp"
    assert s.APP_ENV == "production"
    assert s.DEBUG is False
    assert s.API_V1_PREFIX == "/v2"
    assert s.DATABASE_URL.startswith("postgresql+asyncpg://")
    assert s.GEMINI_API_KEY == "test-gemini-key"
    assert s.CORS_ORIGINS == ["https://codepilot-ai-1-pjss.onrender.com"]


def test_shared_instance_reflects_env(monkeypatch) -> None:
    # monkeypatch env before reloading the shared settings instance
    monkeypatch.setenv("APP_NAME", "SharedApp")
    # Recreate settings instance to reflect env change
    s = Settings()
    assert s.APP_NAME == "SharedApp"
    # The module-level `settings` was created at import time and may not reflect
    # runtime monkeypatch; ensure it's an instance of Settings
    assert isinstance(settings, Settings)


def test_production_requires_explicit_runtime_settings(monkeypatch) -> None:
    for name in ("DATABASE_URL", "GEMINI_API_KEY", "CORS_ORIGINS"):
        monkeypatch.delenv(name, raising=False)

    try:
        Settings(_env_file=None, APP_ENV="production", DEBUG=False)
    except ValueError as error:
        message = str(error)
        assert "DATABASE_URL" in message
    else:
        raise AssertionError("Expected missing production settings to fail")


def test_production_accepts_safe_explicit_settings() -> None:
    production = Settings(
        _env_file=None,
        APP_ENV="production",
        DEBUG=False,
        DATABASE_URL="postgresql+asyncpg://service:password@db.example.com/codepilot",
        GEMINI_API_KEY="test-only-key",
        CORS_ORIGINS=["https://app.example.com"],
    )

    assert production.APP_ENV == "production"
    assert production.DEBUG is False
    assert production.CORS_ORIGINS == ["https://app.example.com"]
    assert production.GEMINI_API_KEY == "test-only-key"


def test_production_requires_explicit_cors_origins() -> None:
    try:
        Settings(
            _env_file=None,
            APP_ENV="production",
            DEBUG=False,
            DATABASE_URL="postgresql+asyncpg://service:password@db.example.com/codepilot",
            GEMINI_API_KEY="test-only-key",
        )
    except ValueError as error:
        assert "CORS_ORIGINS" in str(error)
    else:
        raise AssertionError("Expected production CORS configuration to be required")


def test_wildcard_cors_is_rejected() -> None:
    try:
        Settings(CORS_ORIGINS=["*"])
    except ValueError as error:
        assert "wildcard" in str(error)
    else:
        raise AssertionError("Expected wildcard CORS to fail")


def test_managed_postgres_url_is_normalized_for_asyncpg() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgres://service:password@db.example.com:5432/codepilot",
    )

    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")
    assert "db.example.com:5432/codepilot" in settings.DATABASE_URL


def test_provider_sslmode_is_translated_for_asyncpg() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL=(
            "postgresql://service:password@db.example.com:5432/codepilot"
            "?sslmode=require"
        ),
    )

    assert settings.DATABASE_SSL_MODE == "require"
    assert "ssl=require" in settings.DATABASE_URL
    assert "sslmode" not in settings.DATABASE_URL


def test_database_ssl_mode_can_be_configured_separately() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://service:password@db.example.com/codepilot",
        DATABASE_SSL_MODE="require",
    )

    assert "ssl=require" in settings.DATABASE_URL

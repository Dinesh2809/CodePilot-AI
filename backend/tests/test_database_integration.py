import asyncio

from sqlalchemy import text

from backend.app.core.config import Settings
from backend.app.db.models import CodeChunkRecord
from backend.app.db.session import engine


def test_database_url_setting_from_env(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:codepilot_dev_password@localhost:5433/codepilot",
    )
    settings = Settings()
    assert settings.DATABASE_URL == (
        "postgresql+asyncpg://postgres:codepilot_dev_password@localhost:5433/codepilot"
    )


def test_sqlalchemy_engine_connects_and_vector_column_is_recognized() -> None:
    assert engine is not None

    async def _check() -> None:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar_one() == 1
            await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))

    asyncio.run(_check())


def test_codechunk_model_uses_384_dim_vector() -> None:
    column = CodeChunkRecord.__table__.c.embedding
    assert "384" in str(column.type)

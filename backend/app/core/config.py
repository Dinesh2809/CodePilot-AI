from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Application configuration loaded from environment and optional .env file."""

    APP_NAME: str = "CodePilot AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    MAX_UPLOAD_SIZE_MB: int = Field(default=5, gt=0, le=100)
    MAX_FILES_PER_BATCH: int = Field(default=50, gt=0, le=1000)
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    DATABASE_URL: str = ""
    DATABASE_SSL_MODE: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"
    GEMINI_TIMEOUT_SECONDS: float = Field(default=60.0, gt=0, le=300)
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    CORS_ALLOW_CREDENTIALS: bool = False

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_scheme(cls, value: str) -> str:
        if not value:
            return value
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgresql://")
        return value

    @model_validator(mode="after")
    def validate_environment(self) -> "Settings":
        if self.DATABASE_URL:
            database_url = make_url(self.DATABASE_URL)
            query = dict(database_url.query)
            ssl_mode = query.pop("sslmode", "")
            if ssl_mode and not self.DATABASE_SSL_MODE:
                self.DATABASE_SSL_MODE = ssl_mode
            if self.DATABASE_SSL_MODE:
                query["ssl"] = self.DATABASE_SSL_MODE
            if ssl_mode or self.DATABASE_SSL_MODE:
                self.DATABASE_URL = str(database_url.set(query=query))

        if "*" in self.CORS_ORIGINS:
            raise ValueError("CORS_ORIGINS must not contain a wildcard origin.")

        if self.APP_ENV.lower() in {"prod", "production"}:
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production.")
            if not self.DATABASE_URL:
                raise ValueError("DATABASE_URL is required in production.")
            if not self.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY is required in production.")
            if "CORS_ORIGINS" not in self.model_fields_set or not self.CORS_ORIGINS:
                raise ValueError("CORS_ORIGINS must be configured in production.")

        return self


# Single shared settings instance
settings = Settings()

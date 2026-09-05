from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Application configuration loaded from environment and optional .env file."""

    APP_NAME: str = "CodePilot AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    MAX_UPLOAD_SIZE_MB: int = 5
    MAX_FILES_PER_BATCH: int = 50
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    DATABASE_URL: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
    )


# Single shared settings instance
settings = Settings()

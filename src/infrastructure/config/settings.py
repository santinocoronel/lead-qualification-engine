from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "Lead Qualification Engine"
    app_version: str = "1.0.0"
    debug: bool = False

    database_url: PostgresDsn = Field(
        description="PostgreSQL async connection string (postgresql+asyncpg://...)"
    )
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=100)

    gemini_api_key: str = Field(description="Google Gemini API key")
    gemini_model: str = Field(default="gemini-2.0-flash")
    llm_timeout_seconds: int = Field(default=30, ge=5, le=120)
    llm_max_retries: int = Field(default=3, ge=1, le=10, description="Max retry attempts on transient LLM failures")
    llm_retry_base_delay: float = Field(default=1.0, ge=0.1, le=10.0, description="Base delay in seconds for exponential backoff")

    cors_origins: list[str] = Field(default=["*"])
    api_rate_limit: int = Field(default=60, description="Requests per minute per IP")

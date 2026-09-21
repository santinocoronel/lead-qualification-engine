from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "AI Context Engine"
    app_version: str = "2.0.0"
    base_url: str = Field(default="https://lead-qualification-engine-4ltk.onrender.com")
    debug: bool = False

    database_url: PostgresDsn = Field(
        description="PostgreSQL async connection string (postgresql+asyncpg://...)"
    )
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=100)

    gemini_api_key: str = Field(description="Google Gemini API key")
    gemini_model: str = Field(default="gemini-3.8-flash")
    llm_timeout_seconds: int = Field(default=30, ge=5, le=120)
    llm_max_retries: int = Field(default=3, ge=1, le=10)
    llm_retry_base_delay: float = Field(default=1.0, ge=0.1, le=10.0)

    cors_origins: list[str] = Field(default=["*"])
    api_rate_limit: int = Field(default=60, description="Requests per minute per IP")

    lemonsqueezy_webhook_secret: str = Field(default="")

    paypro_secret_key: str = Field(default="", description="PayPro Global IPN secret key")

    resend_api_key: str = Field(default="", description="Resend API key for transactional emails")
    resend_from_email: str = Field(default="AI Context Engine <noreply@aicontextengine.com>")

    jwt_secret_key: str = Field(default="change-me-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=15)
    jwt_refresh_token_expire_days: int = Field(default=7)

    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_username: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from_email: str = Field(default="noreply@aicontextengine.com")

    fernet_key: str = Field(default="", description="Fernet key for BYOK encryption")

    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

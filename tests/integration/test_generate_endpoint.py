from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.middleware.api_key_auth import require_metered_api_key

# Regression coverage for the bug where /generate-code and /review-code had
# no platform authentication at all: anyone could call them with their own
# LLM provider key and generate unlimited code without an account, a plan,
# or any quota being enforced. See api_key_auth.require_metered_api_key.


def _valid_generate_payload() -> dict[str, object]:
    return {
        "provider": "openai",
        "api_key": "sk-provider-key-does-not-matter-here",
        "context": {"language": "python_3.12", "framework": "fastapi", "rules": ["strict_typing"]},
        "task_description": "Write a health check endpoint.",
    }


def _valid_review_payload() -> dict[str, object]:
    return {
        "provider": "openai",
        "api_key": "sk-provider-key-does-not-matter-here",
        "context": {"language": "python_3.12", "framework": "fastapi", "rules": []},
        "code": "def add(a, b): return a + b",
    }


async def _fake_stream(*args: object, **kwargs: object) -> AsyncIterator[str]:
    for chunk in ("def ", "health(): ", "return 'ok'"):
        yield chunk


@pytest.fixture()
def app_settings() -> MagicMock:
    mock_settings = MagicMock()
    mock_settings.app_name = "Test App"
    mock_settings.app_version = "1.0.0-test"
    mock_settings.debug = False
    mock_settings.cors_origins = ["*"]
    mock_settings.database_url = "postgresql+asyncpg://test:test@localhost/test"
    mock_settings.db_pool_size = 5
    mock_settings.db_max_overflow = 10
    mock_settings.api_rate_limit = 1000
    mock_settings.lemonsqueezy_webhook_secret = ""
    mock_settings.log_level = "WARNING"
    mock_settings.log_format = "json"
    mock_settings.jwt_secret_key = "test-secret"
    mock_settings.jwt_algorithm = "HS256"
    mock_settings.jwt_access_token_expire_minutes = 15
    mock_settings.jwt_refresh_token_expire_days = 7
    mock_settings.smtp_host = ""
    mock_settings.smtp_port = 587
    mock_settings.smtp_username = ""
    mock_settings.smtp_password = ""
    mock_settings.smtp_from_email = "test@test.com"
    mock_settings.fernet_key = ""
    return mock_settings


class TestGenerateCodeAuth:
    def test_no_api_key_header_is_rejected(self, app_settings: MagicMock) -> None:
        with patch("src.api.app.Settings", return_value=app_settings):
            app = create_app()
            with TestClient(app) as client:
                response = client.post("/api/v1/generate-code", json=_valid_generate_payload())
        assert response.status_code == 401

    def test_no_api_key_header_is_rejected_for_review(self, app_settings: MagicMock) -> None:
        with patch("src.api.app.Settings", return_value=app_settings):
            app = create_app()
            with TestClient(app) as client:
                response = client.post("/api/v1/review-code", json=_valid_review_payload())
        assert response.status_code == 401

    def test_valid_platform_key_reaches_generation(self, app_settings: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.owner_email = "dev@example.com"

        with patch("src.api.app.Settings", return_value=app_settings):
            app = create_app()
            app.dependency_overrides[require_metered_api_key] = lambda: mock_client
            with TestClient(app) as client, patch(
                "src.api.v1.generate_router.stream_code_generation", side_effect=_fake_stream
            ):
                response = client.post("/api/v1/generate-code", json=_valid_generate_payload())

        assert response.status_code == 200
        assert "def " in response.text
        assert '"done": true' in response.text

    def test_invalid_provider_returns_400_when_authenticated(self, app_settings: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.owner_email = "dev@example.com"

        with patch("src.api.app.Settings", return_value=app_settings):
            app = create_app()
            app.dependency_overrides[require_metered_api_key] = lambda: mock_client
            with TestClient(app) as client:
                payload = _valid_generate_payload()
                payload["provider"] = "not-a-real-provider"
                response = client.post("/api/v1/generate-code", json=payload)

        assert response.status_code == 400

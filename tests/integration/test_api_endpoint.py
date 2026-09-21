from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_use_case
from src.api.middleware.api_key_auth import require_api_key
from src.application.use_cases.ingest_and_qualify_lead import (
    IngestAndQualifyLeadUseCase,
    QualifiedLeadResult,
)
from src.domain.errors.domain_errors import LLMProviderError, LLMResponseValidationError


def _valid_payload() -> dict[str, str]:
    return {
        "company_name": "Acme Logistics",
        "contact_email": "ops@acme.com",
        "inquiry_text": "We need to automate extraction of 5000 daily PDF remittances.",
        "source": "web_form",
    }


def _success_result() -> QualifiedLeadResult:
    return QualifiedLeadResult(
        lead_id="a8f3b2c1-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
        status="QUALIFIED",
        score=92,
        urgency="HIGH",
        extracted_budget_estimate="medium_enterprise",
        ai_summary="Requires OCR pipeline at scale with 30-day urgency.",
        processed_at="2026-09-20T21:30:00+00:00",
    )


@pytest.fixture()
def mock_use_case() -> AsyncMock:
    return AsyncMock(spec=IngestAndQualifyLeadUseCase)


@pytest.fixture()
def client(mock_use_case: AsyncMock) -> TestClient:
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

    with patch("src.api.app.Settings", return_value=mock_settings):
        app = create_app()

        def _override() -> IngestAndQualifyLeadUseCase:
            return mock_use_case  # type: ignore[return-value]

        app.dependency_overrides[get_use_case] = _override
        mock_client = MagicMock()
        mock_client.subscription_status = "ACTIVE"
        mock_client.monthly_requests_used = 0
        mock_client.monthly_requests_limit = 5000
        mock_client.plan_tier = "PRO"
        app.dependency_overrides[require_api_key] = lambda: mock_client
        with TestClient(app) as tc:
            yield tc


class TestIngestEndpoint:
    def test_successful_ingestion(
        self, client: TestClient, mock_use_case: AsyncMock
    ) -> None:
        mock_use_case.execute.return_value = _success_result()

        response = client.post("/api/v1/leads/ingest", json=_valid_payload())

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "QUALIFIED"
        assert body["score"] == 92
        assert body["lead_id"] == "a8f3b2c1-4d5e-6f7a-8b9c-0d1e2f3a4b5c"
        assert "X-Request-ID" in response.headers

    def test_invalid_email_returns_422(self, client: TestClient) -> None:
        payload = _valid_payload()
        payload["contact_email"] = "not-an-email"

        response = client.post("/api/v1/leads/ingest", json=payload)
        assert response.status_code == 422

    def test_missing_required_field_returns_422(self, client: TestClient) -> None:
        payload = _valid_payload()
        del payload["company_name"]

        response = client.post("/api/v1/leads/ingest", json=payload)
        assert response.status_code == 422

    def test_inquiry_too_short_returns_422(self, client: TestClient) -> None:
        payload = _valid_payload()
        payload["inquiry_text"] = "short"

        response = client.post("/api/v1/leads/ingest", json=payload)
        assert response.status_code == 422

    def test_llm_provider_failure_returns_502(
        self, client: TestClient, mock_use_case: AsyncMock
    ) -> None:
        mock_use_case.execute.side_effect = LLMProviderError("Connection timeout")

        response = client.post("/api/v1/leads/ingest", json=_valid_payload())

        assert response.status_code == 502
        body = response.json()
        assert body["error_code"] == "LLM_PROVIDER_FAILURE"

    def test_llm_response_validation_failure_returns_502(
        self, client: TestClient, mock_use_case: AsyncMock
    ) -> None:
        mock_use_case.execute.side_effect = LLMResponseValidationError(
            "Missing required field 'score'"
        )

        response = client.post("/api/v1/leads/ingest", json=_valid_payload())

        assert response.status_code == 502
        body = response.json()
        assert body["error_code"] == "LLM_RESPONSE_VALIDATION_ERROR"


class TestHealthEndpoints:
    def test_ping(self, client: TestClient) -> None:
        response = client.get("/ping")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_check(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["version"] == "1.0.0-test"
        assert body["status"] in ("healthy", "degraded")

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Depends, status
from fastapi.testclient import TestClient

from src.api.middleware.api_key_auth import hash_api_key, require_api_key, invalidate_cache


def _mock_client_record(
    subscription_status: str = "ACTIVE",
    monthly_requests_used: int = 0,
    monthly_requests_limit: int = 5000,
    plan_tier: str = "PRO",
) -> MagicMock:
    record = MagicMock()
    record.id = "fake-uuid"
    record.owner_email = "user@example.com"
    record.api_key_hash = hash_api_key("valid-key-123")
    record.plan_tier = plan_tier
    record.subscription_status = subscription_status
    record.monthly_requests_used = monthly_requests_used
    record.monthly_requests_limit = monthly_requests_limit
    record.encrypted_api_key = None
    record.custom_llm_provider = None
    record.alert_80_sent_at = None
    record.alert_95_sent_at = None
    return record


def _build_mock_session(return_client: MagicMock | None) -> AsyncMock:
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = return_client
    mock_session.execute.return_value = mock_result
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_begin = MagicMock()
    mock_begin.__aenter__ = AsyncMock(return_value=None)
    mock_begin.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin = MagicMock(return_value=mock_begin)

    return mock_session


def _build_app() -> FastAPI:
    app = FastAPI()
    app.state.session_factory = MagicMock()

    @app.get("/protected", dependencies=[Depends(require_api_key)])
    async def protected() -> dict[str, str]:
        return {"status": "ok"}

    return app


class TestHashApiKey:
    def test_deterministic(self) -> None:
        assert hash_api_key("test-key-123") == hash_api_key("test-key-123")

    def test_different_keys_different_hashes(self) -> None:
        assert hash_api_key("key-a") != hash_api_key("key-b")


class TestRequireApiKey:
    def setup_method(self) -> None:
        invalidate_cache()

    def test_missing_header_returns_401(self) -> None:
        app = _build_app()
        client = TestClient(app)
        response = client.get("/protected")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unknown_key_returns_403(self) -> None:
        app = _build_app()
        mock_session = _build_mock_session(return_client=None)
        app.state.session_factory.return_value = mock_session

        client = TestClient(app)
        response = client.get("/protected", headers={"X-API-Key": "invalid-key"})
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Invalid API key" in response.json()["detail"]

    def test_inactive_subscription_returns_403(self) -> None:
        app = _build_app()
        record = _mock_client_record(subscription_status="INACTIVE")
        mock_session = _build_mock_session(return_client=record)
        app.state.session_factory.return_value = mock_session

        client = TestClient(app)
        response = client.get("/protected", headers={"X-API-Key": "valid-key-123"})
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "INACTIVE" in response.json()["detail"]

    def test_past_due_subscription_returns_403(self) -> None:
        app = _build_app()
        record = _mock_client_record(subscription_status="PAST_DUE")
        mock_session = _build_mock_session(return_client=record)
        app.state.session_factory.return_value = mock_session

        client = TestClient(app)
        response = client.get("/protected", headers={"X-API-Key": "valid-key-123"})
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "PAST_DUE" in response.json()["detail"]

    def test_quota_exceeded_returns_429(self) -> None:
        app = _build_app()
        record = _mock_client_record(
            subscription_status="ACTIVE",
            monthly_requests_used=5000,
            monthly_requests_limit=5000,
        )
        mock_session = _build_mock_session(return_client=record)
        app.state.session_factory.return_value = mock_session

        client = TestClient(app)
        response = client.get("/protected", headers={"X-API-Key": "valid-key-123"})
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "Upgrade" in response.json()["detail"]

    def test_active_subscription_with_quota_passes(self) -> None:
        app = _build_app()
        record = _mock_client_record(
            subscription_status="ACTIVE",
            monthly_requests_used=10,
            monthly_requests_limit=5000,
        )
        mock_session = _build_mock_session(return_client=record)
        app.state.session_factory.return_value = mock_session

        client = TestClient(app)
        response = client.get("/protected", headers={"X-API-Key": "valid-key-123"})
        assert response.status_code == status.HTTP_200_OK

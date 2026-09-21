from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.middleware.api_key_auth import invalidate_cache


def _make_mock_settings(webhook_secret: str = "lsq_test_secret") -> MagicMock:
    s = MagicMock()
    s.app_name = "Test App"
    s.app_version = "1.0.0-test"
    s.debug = False
    s.cors_origins = ["*"]
    s.database_url = "postgresql+asyncpg://test:test@localhost/test"
    s.db_pool_size = 5
    s.db_max_overflow = 10
    s.api_rate_limit = 1000
    s.lemonsqueezy_webhook_secret = webhook_secret
    s.log_level = "WARNING"
    s.log_format = "json"
    s.jwt_secret_key = "test-secret"
    s.jwt_algorithm = "HS256"
    s.jwt_access_token_expire_minutes = 15
    s.jwt_refresh_token_expire_days = 7
    s.smtp_host = ""
    s.smtp_port = 587
    s.smtp_username = ""
    s.smtp_password = ""
    s.smtp_from_email = "test@test.com"
    s.fernet_key = ""
    s.resend_api_key = ""
    s.resend_from_email = ""
    s.base_url = "http://localhost:8000"
    return s


def _make_client(webhook_secret: str = "lsq_test_secret") -> TestClient:
    with patch("src.api.app.Settings", return_value=_make_mock_settings(webhook_secret)):
        app = create_app()
        return TestClient(app)


def _sign_payload(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _make_event(
    event_name: str,
    user_email: str = "user@example.com",
    variant: str = "Pro",
) -> dict:
    return {
        "meta": {
            "event_name": event_name,
            "custom_data": {"user_email": user_email},
        },
        "data": {
            "id": "sub_123",
            "attributes": {
                "status": "active",
                "user_email": user_email,
                "variant_name": variant,
            },
        },
    }


def _build_mock_session_factory() -> tuple[MagicMock, AsyncMock]:
    mock_session = AsyncMock()

    mock_begin_ctx = MagicMock()
    mock_begin_ctx.__aenter__ = AsyncMock(return_value=None)
    mock_begin_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin = MagicMock(return_value=mock_begin_ctx)

    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_session)
    return mock_factory, mock_session


class TestLemonSqueezyWebhook:
    def setup_method(self) -> None:
        invalidate_cache()

    def test_missing_signature_returns_400(self) -> None:
        client = _make_client()
        response = client.post("/api/v1/billing/webhook", json=_make_event("subscription_created"))
        assert response.status_code == 400

    def test_invalid_signature_returns_400(self) -> None:
        client = _make_client()
        response = client.post(
            "/api/v1/billing/webhook",
            json=_make_event("subscription_created"),
            headers={"X-Signature": "invalid_hex"},
        )
        assert response.status_code == 400

    def test_valid_signature_unhandled_event_returns_200(self) -> None:
        secret = "lsq_test_secret"
        client = _make_client(webhook_secret=secret)
        payload = json.dumps(_make_event("charge_created")).encode()
        sig = _sign_payload(payload, secret)
        response = client.post(
            "/api/v1/billing/webhook",
            content=payload,
            headers={"X-Signature": sig, "Content-Type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_unconfigured_secret_returns_500(self) -> None:
        client = _make_client(webhook_secret="")
        response = client.post(
            "/api/v1/billing/webhook",
            json=_make_event("subscription_created"),
            headers={"X-Signature": "whatever"},
        )
        assert response.status_code == 500

    def test_subscription_created_activates_client(self) -> None:
        secret = "lsq_test_secret"
        mock_factory, mock_session = _build_mock_session_factory()

        mock_client = MagicMock()
        mock_client.id = "fake-uuid"
        mock_client.api_key_hash = "fakehash"
        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = mock_client
        mock_update_result = MagicMock()
        mock_update_result.rowcount = 1
        mock_session.execute = AsyncMock(side_effect=[mock_select_result, mock_update_result])

        with patch("src.api.app.Settings", return_value=_make_mock_settings(secret)):
            app = create_app()
            app.state.session_factory = mock_factory
            app.state.email_adapter = AsyncMock()

            tc = TestClient(app)
            payload = json.dumps(_make_event("subscription_created", "test@co.com", "Pro")).encode()
            sig = _sign_payload(payload, secret)
            response = tc.post(
                "/api/v1/billing/webhook",
                content=payload,
                headers={"X-Signature": sig, "Content-Type": "application/json"},
            )
            assert response.status_code == 200
            assert mock_session.execute.await_count >= 1

    def test_order_created_activates_client(self) -> None:
        secret = "lsq_test_secret"
        mock_factory, mock_session = _build_mock_session_factory()

        mock_client = MagicMock()
        mock_client.id = "fake-uuid"
        mock_client.api_key_hash = "fakehash"
        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = mock_client
        mock_update_result = MagicMock()
        mock_session.execute = AsyncMock(side_effect=[mock_select_result, mock_update_result])

        with patch("src.api.app.Settings", return_value=_make_mock_settings(secret)):
            app = create_app()
            app.state.session_factory = mock_factory
            app.state.email_adapter = AsyncMock()

            tc = TestClient(app)
            payload = json.dumps(_make_event("order_created", "test@co.com", "Agency")).encode()
            sig = _sign_payload(payload, secret)
            response = tc.post(
                "/api/v1/billing/webhook",
                content=payload,
                headers={"X-Signature": sig, "Content-Type": "application/json"},
            )
            assert response.status_code == 200

    def test_subscription_expired_sets_inactive(self) -> None:
        secret = "lsq_test_secret"
        mock_factory, mock_session = _build_mock_session_factory()

        mock_client = MagicMock()
        mock_client.id = "fake-uuid"
        mock_client.api_key_hash = "fakehash"
        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = mock_client
        mock_update_result = MagicMock()
        mock_session.execute = AsyncMock(side_effect=[mock_select_result, mock_update_result])

        with patch("src.api.app.Settings", return_value=_make_mock_settings(secret)):
            app = create_app()
            app.state.session_factory = mock_factory
            app.state.email_adapter = AsyncMock()

            tc = TestClient(app)
            payload = json.dumps(_make_event("subscription_expired", "test@co.com")).encode()
            sig = _sign_payload(payload, secret)
            response = tc.post(
                "/api/v1/billing/webhook",
                content=payload,
                headers={"X-Signature": sig, "Content-Type": "application/json"},
            )
            assert response.status_code == 200

    def test_payment_failed_sets_past_due(self) -> None:
        secret = "lsq_test_secret"
        mock_factory, mock_session = _build_mock_session_factory()

        mock_client = MagicMock()
        mock_client.id = "fake-uuid"
        mock_client.api_key_hash = "fakehash"
        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = mock_client
        mock_update_result = MagicMock()
        mock_session.execute = AsyncMock(side_effect=[mock_select_result, mock_update_result])

        with patch("src.api.app.Settings", return_value=_make_mock_settings(secret)):
            app = create_app()
            app.state.session_factory = mock_factory
            app.state.email_adapter = AsyncMock()

            tc = TestClient(app)
            payload = json.dumps(_make_event("subscription_payment_failed", "test@co.com")).encode()
            sig = _sign_payload(payload, secret)
            response = tc.post(
                "/api/v1/billing/webhook",
                content=payload,
                headers={"X-Signature": sig, "Content-Type": "application/json"},
            )
            assert response.status_code == 200

    def test_subscription_cancelled_sets_canceled(self) -> None:
        secret = "lsq_test_secret"
        mock_factory, mock_session = _build_mock_session_factory()

        mock_client = MagicMock()
        mock_client.id = "fake-uuid"
        mock_client.api_key_hash = "fakehash"
        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = mock_client
        mock_update_result = MagicMock()
        mock_session.execute = AsyncMock(side_effect=[mock_select_result, mock_update_result])

        with patch("src.api.app.Settings", return_value=_make_mock_settings(secret)):
            app = create_app()
            app.state.session_factory = mock_factory
            app.state.email_adapter = AsyncMock()

            tc = TestClient(app)
            payload = json.dumps(_make_event("subscription_cancelled", "test@co.com")).encode()
            sig = _sign_payload(payload, secret)
            response = tc.post(
                "/api/v1/billing/webhook",
                content=payload,
                headers={"X-Signature": sig, "Content-Type": "application/json"},
            )
            assert response.status_code == 200

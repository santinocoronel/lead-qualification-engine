from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.middleware.api_key_auth import invalidate_cache


def _make_mock_settings() -> MagicMock:
    s = MagicMock()
    s.app_name = "Test App"
    s.app_version = "1.0.0-test"
    s.debug = False
    s.cors_origins = ["*"]
    s.database_url = "postgresql+asyncpg://test:test@localhost/test"
    s.db_pool_size = 5
    s.db_max_overflow = 10
    s.api_rate_limit = 1000
    s.lemonsqueezy_webhook_secret = ""
    s.log_level = "WARNING"
    s.log_format = "json"
    s.jwt_secret_key = "test-secret-key-for-jwt"
    s.jwt_algorithm = "HS256"
    s.jwt_access_token_expire_minutes = 15
    s.jwt_refresh_token_expire_days = 7
    s.smtp_host = ""
    s.smtp_port = 587
    s.smtp_username = ""
    s.smtp_password = ""
    s.smtp_from_email = "test@test.com"
    s.fernet_key = ""
    return s


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


class TestRegister:
    def setup_method(self) -> None:
        invalidate_cache()

    def test_register_success(self) -> None:
        mock_factory, mock_session = _build_mock_session_factory()

        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_select_result)

        with patch("src.api.app.Settings", return_value=_make_mock_settings()):
            app = create_app()
            app.state.session_factory = mock_factory

            tc = TestClient(app)
            response = tc.post(
                "/api/v1/auth/register",
                json={"email": "new@example.com", "password": "securepass123"},
            )
            assert response.status_code == 201
            body = response.json()
            assert body["email"] == "new@example.com"
            assert body["plan_tier"] == "FREE"
            assert "api_key" in body
            assert len(body["api_key"]) > 20

    def test_register_duplicate_email_returns_409(self) -> None:
        mock_factory, mock_session = _build_mock_session_factory()

        existing_client = MagicMock()
        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = existing_client
        mock_session.execute = AsyncMock(return_value=mock_select_result)

        with patch("src.api.app.Settings", return_value=_make_mock_settings()):
            app = create_app()
            app.state.session_factory = mock_factory

            tc = TestClient(app)
            response = tc.post(
                "/api/v1/auth/register",
                json={"email": "dup@example.com", "password": "securepass123"},
            )
            assert response.status_code == 409

    def test_register_short_password_returns_422(self) -> None:
        with patch("src.api.app.Settings", return_value=_make_mock_settings()):
            app = create_app()
            tc = TestClient(app)
            response = tc.post(
                "/api/v1/auth/register",
                json={"email": "short@example.com", "password": "short"},
            )
            assert response.status_code == 422


class TestLogin:
    def setup_method(self) -> None:
        invalidate_cache()

    def test_login_success(self) -> None:
        import bcrypt

        hashed = bcrypt.hashpw(b"correctpassword", bcrypt.gensalt()).decode()

        mock_factory, mock_session = _build_mock_session_factory()
        mock_client = MagicMock()
        mock_client.id = "fake-uuid"
        mock_client.owner_email = "user@example.com"
        mock_client.password_hash = hashed

        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = mock_client
        mock_session.execute = AsyncMock(return_value=mock_select_result)

        with patch("src.api.app.Settings", return_value=_make_mock_settings()):
            app = create_app()
            app.state.session_factory = mock_factory

            tc = TestClient(app)
            response = tc.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": "correctpassword"},
            )
            assert response.status_code == 200
            body = response.json()
            assert "access_token" in body
            assert "refresh_token" in body
            assert body["token_type"] == "bearer"

    def test_login_wrong_password_returns_401(self) -> None:
        import bcrypt

        hashed = bcrypt.hashpw(b"correctpassword", bcrypt.gensalt()).decode()

        mock_factory, mock_session = _build_mock_session_factory()
        mock_client = MagicMock()
        mock_client.id = "fake-uuid"
        mock_client.owner_email = "user@example.com"
        mock_client.password_hash = hashed

        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = mock_client
        mock_session.execute = AsyncMock(return_value=mock_select_result)

        with patch("src.api.app.Settings", return_value=_make_mock_settings()):
            app = create_app()
            app.state.session_factory = mock_factory

            tc = TestClient(app)
            response = tc.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": "wrongpassword"},
            )
            assert response.status_code == 401

    def test_login_unknown_email_returns_401(self) -> None:
        mock_factory, mock_session = _build_mock_session_factory()
        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_select_result)

        with patch("src.api.app.Settings", return_value=_make_mock_settings()):
            app = create_app()
            app.state.session_factory = mock_factory

            tc = TestClient(app)
            response = tc.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": "anypassword"},
            )
            assert response.status_code == 401


class TestForgotPassword:
    def test_forgot_password_returns_message(self) -> None:
        mock_factory, mock_session = _build_mock_session_factory()

        mock_client = MagicMock()
        mock_client.id = "fake-uuid"
        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = mock_client
        mock_session.execute = AsyncMock(side_effect=[mock_select_result, MagicMock()])

        with patch("src.api.app.Settings", return_value=_make_mock_settings()):
            app = create_app()
            app.state.session_factory = mock_factory
            app.state.email_adapter = AsyncMock()

            tc = TestClient(app)
            response = tc.post(
                "/api/v1/auth/forgot-password",
                json={"email": "user@example.com"},
            )
            assert response.status_code == 200
            assert "reset link" in response.json()["message"].lower()

    def test_forgot_password_unknown_email_still_returns_200(self) -> None:
        mock_factory, mock_session = _build_mock_session_factory()

        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_select_result)

        with patch("src.api.app.Settings", return_value=_make_mock_settings()):
            app = create_app()
            app.state.session_factory = mock_factory
            app.state.email_adapter = AsyncMock()

            tc = TestClient(app)
            response = tc.post(
                "/api/v1/auth/forgot-password",
                json={"email": "nobody@example.com"},
            )
            assert response.status_code == 200


class TestResetPassword:
    def test_reset_password_invalid_token_returns_400(self) -> None:
        mock_factory, mock_session = _build_mock_session_factory()

        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_select_result)

        with patch("src.api.app.Settings", return_value=_make_mock_settings()):
            app = create_app()
            app.state.session_factory = mock_factory

            tc = TestClient(app)
            response = tc.post(
                "/api/v1/auth/reset-password",
                json={"token": "invalid-token", "new_password": "newsecurepass"},
            )
            assert response.status_code == 400

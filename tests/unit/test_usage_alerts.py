from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.services.usage_alert_service import check_usage_alerts


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


def _mock_client(
    used: int = 0,
    limit: int = 100,
    alert_80: object = None,
    alert_95: object = None,
) -> MagicMock:
    client = MagicMock()
    client.id = "fake-uuid"
    client.owner_email = "test@example.com"
    client.plan_tier = "FREE"
    client.monthly_requests_used = used
    client.monthly_requests_limit = limit
    client.alert_80_sent_at = alert_80
    client.alert_95_sent_at = alert_95
    return client


class TestUsageAlerts:
    @pytest.mark.asyncio
    async def test_no_alert_below_80_percent(self) -> None:
        email_adapter = AsyncMock()
        sf, _ = _build_mock_session_factory()

        await check_usage_alerts(_mock_client(used=50, limit=100), sf, email_adapter)

        email_adapter.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_alert_at_80_percent(self) -> None:
        email_adapter = AsyncMock()
        sf, session = _build_mock_session_factory()
        session.execute = AsyncMock(return_value=MagicMock())

        await check_usage_alerts(_mock_client(used=80, limit=100), sf, email_adapter)

        email_adapter.send_email.assert_called_once()
        call_args = email_adapter.send_email.call_args
        assert "80%" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_alert_at_95_percent(self) -> None:
        email_adapter = AsyncMock()
        sf, session = _build_mock_session_factory()
        session.execute = AsyncMock(return_value=MagicMock())

        await check_usage_alerts(_mock_client(used=95, limit=100), sf, email_adapter)

        email_adapter.send_email.assert_called_once()
        call_args = email_adapter.send_email.call_args
        assert "95%" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_no_duplicate_80_alert(self) -> None:
        from datetime import datetime, UTC

        email_adapter = AsyncMock()
        sf, _ = _build_mock_session_factory()

        client = _mock_client(used=85, limit=100, alert_80=datetime.now(UTC))

        await check_usage_alerts(client, sf, email_adapter)

        email_adapter.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_duplicate_95_alert(self) -> None:
        from datetime import datetime, UTC

        email_adapter = AsyncMock()
        sf, _ = _build_mock_session_factory()

        client = _mock_client(
            used=96, limit=100, alert_80=datetime.now(UTC), alert_95=datetime.now(UTC)
        )

        await check_usage_alerts(client, sf, email_adapter)

        email_adapter.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_zero_limit_no_alert(self) -> None:
        email_adapter = AsyncMock()
        sf, _ = _build_mock_session_factory()

        await check_usage_alerts(_mock_client(used=0, limit=0), sf, email_adapter)

        email_adapter.send_email.assert_not_called()

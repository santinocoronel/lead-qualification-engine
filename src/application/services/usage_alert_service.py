from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import update

from src.domain.ports.email_port import EmailPort
from src.infrastructure.email.templates import usage_alert_80_email, usage_alert_95_email
from src.infrastructure.persistence.client_model import ClientModel

logger = structlog.get_logger(__name__)

_80_PERCENT = 0.80
_95_PERCENT = 0.95

async def check_usage_alerts(
    client: ClientModel,
    session_factory: object,
    email_adapter: EmailPort,
    base_url: str = "",
) -> None:
    if client.monthly_requests_limit <= 0:
        return

    usage_ratio = client.monthly_requests_used / client.monthly_requests_limit

    if usage_ratio >= _95_PERCENT and client.alert_95_sent_at is None:
        await _send_alert(client, 95, session_factory, email_adapter, base_url)
    elif usage_ratio >= _80_PERCENT and client.alert_80_sent_at is None:
        await _send_alert(client, 80, session_factory, email_adapter, base_url)


async def _send_alert(
    client: ClientModel,
    threshold: int,
    session_factory: object,
    email_adapter: EmailPort,
    base_url: str,
) -> None:
    try:
        template_fn = usage_alert_95_email if threshold == 95 else usage_alert_80_email
        subject, body = template_fn(
            client.owner_email, client.monthly_requests_used, client.monthly_requests_limit, base_url,
        )
        await email_adapter.send_email(client.owner_email, subject, body)

        now = datetime.now(UTC)
        column = (
            ClientModel.alert_95_sent_at if threshold == 95 else ClientModel.alert_80_sent_at
        )
        async with session_factory() as session:  # type: ignore[operator]
            async with session.begin():
                await session.execute(
                    update(ClientModel)
                    .where(ClientModel.id == client.id)
                    .values({column: now})
                )

        logger.info(
            "usage_alert_sent",
            owner_email=client.owner_email,
            threshold=threshold,
            used=client.monthly_requests_used,
            limit=client.monthly_requests_limit,
        )
    except Exception:
        logger.exception(
            "usage_alert_failed",
            owner_email=client.owner_email,
            threshold=threshold,
        )

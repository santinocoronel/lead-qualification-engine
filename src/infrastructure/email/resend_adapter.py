from __future__ import annotations

import httpx
import structlog

from src.domain.ports.email_port import EmailPort

logger = structlog.get_logger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


class ResendEmailAdapter(EmailPort):
    def __init__(self, api_key: str, from_email: str) -> None:
        self._api_key = api_key
        self._from_email = from_email

    async def send_email(self, to: str, subject: str, body: str) -> None:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                RESEND_API_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "from": self._from_email,
                    "to": [to],
                    "subject": subject,
                    "html": body,
                },
            )
            if resp.status_code >= 400:
                logger.error(
                    "resend_email_failed",
                    to=to,
                    subject=subject,
                    status=resp.status_code,
                    detail=resp.text,
                )
                return
            logger.info("resend_email_sent", to=to, subject=subject)

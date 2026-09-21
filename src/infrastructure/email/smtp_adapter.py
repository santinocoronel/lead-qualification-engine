from __future__ import annotations

import asyncio
import smtplib
from email.mime.text import MIMEText

import structlog

from src.domain.ports.email_port import EmailPort
from src.infrastructure.config.settings import Settings

logger = structlog.get_logger(__name__)


class ConsoleEmailAdapter(EmailPort):
    async def send_email(self, to: str, subject: str, body: str) -> None:
        logger.info("email_sent_console", to=to, subject=subject, body=body[:200])


class SMTPEmailAdapter(EmailPort):
    def __init__(self, settings: Settings) -> None:
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._username = settings.smtp_username
        self._password = settings.smtp_password
        self._from_email = settings.smtp_from_email

    async def send_email(self, to: str, subject: str, body: str) -> None:
        msg = MIMEText(body, "html")
        msg["Subject"] = subject
        msg["From"] = self._from_email
        msg["To"] = to

        await asyncio.to_thread(self._send_sync, msg)
        logger.info("email_sent_smtp", to=to, subject=subject)

    def _send_sync(self, msg: MIMEText) -> None:
        with smtplib.SMTP(self._host, self._port) as server:
            server.starttls()
            if self._username:
                server.login(self._username, self._password)
            server.send_message(msg)

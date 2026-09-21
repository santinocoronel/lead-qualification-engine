from __future__ import annotations

from abc import ABC, abstractmethod


class EmailPort(ABC):
    @abstractmethod
    async def send_email(self, to: str, subject: str, body: str) -> None: ...

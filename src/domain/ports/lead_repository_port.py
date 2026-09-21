from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.lead import Lead


class LeadRepositoryPort(ABC):
    @abstractmethod
    async def save(self, lead: Lead) -> None: ...

    @abstractmethod
    async def find_by_id(self, lead_id: str) -> Lead | None: ...

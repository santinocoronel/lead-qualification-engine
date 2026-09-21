from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.entities.lead import Lead
from src.domain.ports.lead_repository_port import LeadRepositoryPort
from src.domain.value_objects.email import Email
from src.domain.value_objects.enums import QualificationStatus, UrgencyLevel
from src.domain.value_objects.lead_score import LeadScore
from src.infrastructure.persistence.lead_model import LeadModel


class SQLAlchemyLeadRepository(LeadRepositoryPort):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, lead: Lead) -> None:
        async with self._session_factory() as session, session.begin():
            model = LeadModel(
                lead_id=lead.lead_id,
                company_name=lead.company_name,
                contact_email=str(lead.contact_email),
                inquiry_text=lead.inquiry_text,
                source=lead.source,
                score=lead.score.value,
                urgency=lead.urgency.value,
                status=lead.status.value,
                ai_summary=lead.ai_summary,
                extracted_budget_estimate=lead.extracted_budget_estimate,
                created_at=lead.created_at,
            )
            session.add(model)

    async def find_by_id(self, lead_id: str) -> Lead | None:
        async with self._session_factory() as session:
            stmt = select(LeadModel).where(LeadModel.lead_id == uuid.UUID(lead_id))
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return Lead(
                lead_id=row.lead_id,
                company_name=row.company_name,
                contact_email=Email(row.contact_email),
                inquiry_text=row.inquiry_text,
                source=row.source,
                score=LeadScore(row.score),
                urgency=UrgencyLevel(row.urgency),
                status=QualificationStatus(row.status),
                ai_summary=row.ai_summary,
                extracted_budget_estimate=row.extracted_budget_estimate,
                created_at=row.created_at,
            )

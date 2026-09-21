from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from src.domain.entities.lead import Lead
from src.domain.ports.lead_repository_port import LeadRepositoryPort
from src.domain.ports.llm_analyzer_port import LLMAnalyzerPort
from src.domain.value_objects.email import Email
from src.domain.value_objects.lead_score import LeadScore

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class IngestLeadCommand:
    company_name: str
    contact_email: str
    inquiry_text: str
    source: str


@dataclass(frozen=True, slots=True)
class QualifiedLeadResult:
    lead_id: str
    status: str
    score: int
    urgency: str
    extracted_budget_estimate: str
    ai_summary: str
    processed_at: str


class IngestAndQualifyLeadUseCase:
    def __init__(
        self,
        repository: LeadRepositoryPort,
        llm_analyzer: LLMAnalyzerPort,
    ) -> None:
        self._repository = repository
        self._llm_analyzer = llm_analyzer

    async def execute(self, command: IngestLeadCommand) -> QualifiedLeadResult:
        log = logger.bind(
            company=command.company_name,
            source=command.source,
        )
        log.info("lead_ingestion_started")

        analysis = await self._llm_analyzer.analyze_lead(
            company_name=command.company_name,
            inquiry_text=command.inquiry_text,
            source=command.source,
        )

        log.info(
            "llm_analysis_completed",
            score=analysis.score,
            urgency=analysis.urgency,
        )

        status = Lead.determine_status(analysis.score)

        lead = Lead(
            company_name=command.company_name,
            contact_email=Email(command.contact_email),
            inquiry_text=command.inquiry_text,
            source=command.source,
            score=LeadScore(analysis.score),
            urgency=analysis.urgency,
            status=status,
            ai_summary=analysis.summary,
            extracted_budget_estimate=analysis.budget_estimate,
        )

        await self._repository.save(lead)

        log.info(
            "lead_persisted",
            lead_id=str(lead.lead_id),
            status=status,
        )

        return QualifiedLeadResult(
            lead_id=str(lead.lead_id),
            status=lead.status.value,
            score=lead.score.value,
            urgency=lead.urgency.value,
            extracted_budget_estimate=lead.extracted_budget_estimate,
            ai_summary=lead.ai_summary,
            processed_at=datetime.now(UTC).isoformat(),
        )

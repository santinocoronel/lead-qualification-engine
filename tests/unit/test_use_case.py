from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.ingest_and_qualify_lead import (
    IngestAndQualifyLeadUseCase,
    IngestLeadCommand,
)
from src.domain.entities.lead import Lead
from src.domain.errors.domain_errors import LLMProviderError
from src.domain.ports.llm_analyzer_port import LLMAnalysisResult
from src.domain.value_objects.enums import UrgencyLevel


def _make_command() -> IngestLeadCommand:
    return IngestLeadCommand(
        company_name="Acme Logistics",
        contact_email="ops@acme.com",
        inquiry_text="Need to automate 5000 daily PDF extractions.",
        source="web_form",
    )


def _make_analysis(score: int = 92) -> LLMAnalysisResult:
    return LLMAnalysisResult(
        score=score,
        urgency=UrgencyLevel.HIGH,
        budget_estimate="medium_enterprise",
        summary="Requires OCR pipeline at scale.",
    )


class TestIngestAndQualifyLeadUseCase:
    @pytest.fixture()
    def mock_repository(self) -> AsyncMock:
        repo = AsyncMock()
        repo.save = AsyncMock(return_value=None)
        return repo

    @pytest.fixture()
    def mock_llm(self) -> AsyncMock:
        llm = AsyncMock()
        llm.analyze_lead = AsyncMock(return_value=_make_analysis())
        return llm

    async def test_successful_qualification(
        self, mock_repository: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        use_case = IngestAndQualifyLeadUseCase(mock_repository, mock_llm)
        result = await use_case.execute(_make_command())

        assert result.status == "QUALIFIED"
        assert result.score == 92
        assert result.urgency == "HIGH"
        assert result.extracted_budget_estimate == "medium_enterprise"
        mock_repository.save.assert_awaited_once()
        saved_lead: Lead = mock_repository.save.call_args[0][0]
        assert saved_lead.company_name == "Acme Logistics"

    async def test_low_score_disqualifies(
        self, mock_repository: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        mock_llm.analyze_lead.return_value = _make_analysis(score=20)
        use_case = IngestAndQualifyLeadUseCase(mock_repository, mock_llm)
        result = await use_case.execute(_make_command())

        assert result.status == "DISQUALIFIED"
        assert result.score == 20

    async def test_mid_score_needs_review(
        self, mock_repository: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        mock_llm.analyze_lead.return_value = _make_analysis(score=55)
        use_case = IngestAndQualifyLeadUseCase(mock_repository, mock_llm)
        result = await use_case.execute(_make_command())

        assert result.status == "REVIEW_NEEDED"

    async def test_llm_failure_propagates(
        self, mock_repository: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        mock_llm.analyze_lead.side_effect = LLMProviderError("Timeout")
        use_case = IngestAndQualifyLeadUseCase(mock_repository, mock_llm)

        with pytest.raises(LLMProviderError):
            await use_case.execute(_make_command())

        mock_repository.save.assert_not_awaited()

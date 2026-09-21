from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from src.application.use_cases.ingest_and_qualify_lead import IngestAndQualifyLeadUseCase
from src.infrastructure.config.settings import Settings
from src.infrastructure.llm.gemini_analyzer import GeminiLeadAnalyzer
from src.infrastructure.persistence.lead_repository import SQLAlchemyLeadRepository


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def get_use_case(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> IngestAndQualifyLeadUseCase:
    session_factory = request.app.state.session_factory
    repository = SQLAlchemyLeadRepository(session_factory)
    llm_analyzer = GeminiLeadAnalyzer(settings)
    return IngestAndQualifyLeadUseCase(
        repository=repository,
        llm_analyzer=llm_analyzer,
    )

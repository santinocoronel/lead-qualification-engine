from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.api.dependencies import get_use_case
from src.api.v1.schemas import ErrorResponse, IngestLeadRequest, IngestLeadResponse
from src.application.use_cases.ingest_and_qualify_lead import (
    IngestAndQualifyLeadUseCase,
    IngestLeadCommand,
)

router = APIRouter(prefix="/api/v1/leads", tags=["Lead qualification"])


@router.post(
    "/ingest",
    status_code=status.HTTP_201_CREATED,
    response_model=IngestLeadResponse,
    summary="Ingest and qualify a new lead",
    description=(
        "Receives a prospect inquiry, runs it through the AI scoring pipeline "
        "(budget, urgency, technical fit, intent clarity), persists the qualified "
        "lead in PostgreSQL and returns the structured result. "
        "The AI provider is called with retry + exponential backoff."
    ),
    responses={
        201: {"description": "Lead successfully qualified and persisted."},
        400: {"model": ErrorResponse, "description": "Domain validation failed (e.g. empty company name)."},
        422: {"model": ErrorResponse, "description": "Request payload validation failed."},
        500: {"model": ErrorResponse, "description": "Unexpected internal server error."},
        502: {"model": ErrorResponse, "description": "AI provider unreachable or returned invalid data."},
    },
)
async def ingest_lead(
    payload: IngestLeadRequest,
    use_case: Annotated[IngestAndQualifyLeadUseCase, Depends(get_use_case)],
) -> IngestLeadResponse:
    command = IngestLeadCommand(
        company_name=payload.company_name,
        contact_email=payload.contact_email,
        inquiry_text=payload.inquiry_text,
        source=payload.source,
    )
    result = await use_case.execute(command)
    return IngestLeadResponse(
        lead_id=result.lead_id,
        status=result.status,
        score=result.score,
        urgency=result.urgency,
        extracted_budget_estimate=result.extracted_budget_estimate,
        ai_summary=result.ai_summary,
        processed_at=result.processed_at,
    )

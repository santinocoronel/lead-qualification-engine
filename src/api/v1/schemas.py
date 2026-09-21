from pydantic import BaseModel, EmailStr, Field


class IngestLeadRequest(BaseModel):
    """Payload for submitting a new lead to the qualification pipeline."""

    model_config = {"json_schema_extra": {"examples": [
        {
            "company_name": "Acme Logistics",
            "contact_email": "ops@acme.com",
            "inquiry_text": (
                "Necesitamos automatizar la extracción de datos de 5.000 remitos "
                "diarios en PDF y cargarlos en nuestra base de datos. Tenemos "
                "presupuesto asignado y queremos empezar el próximo mes."
            ),
            "source": "web_form",
        }
    ]}}

    company_name: str = Field(
        min_length=1,
        max_length=255,
        description="Legal or trading name of the prospect company.",
    )
    contact_email: EmailStr = Field(
        description="Primary contact email for follow-up.",
    )
    inquiry_text: str = Field(
        min_length=10,
        max_length=10_000,
        description="Free-text inquiry describing the prospect's need.",
    )
    source: str = Field(
        min_length=1,
        max_length=100,
        description="Acquisition channel (e.g. web_form, referral, linkedin, cold_email).",
    )


class IngestLeadResponse(BaseModel):
    """Result of a successfully qualified lead."""

    model_config = {"json_schema_extra": {"examples": [
        {
            "lead_id": "a8f3b2c1-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
            "status": "QUALIFIED",
            "score": 92,
            "urgency": "HIGH",
            "extracted_budget_estimate": "medium_enterprise",
            "ai_summary": (
                "Requiere pipeline RAG/OCR para extracción de remitos a escala "
                "con urgencia de 30 días."
            ),
            "processed_at": "2026-09-20T21:30:00+00:00",
        }
    ]}}

    lead_id: str = Field(description="UUID v4 assigned to the persisted lead.")
    status: str = Field(description="QUALIFIED | DISQUALIFIED | REVIEW_NEEDED")
    score: int = Field(ge=0, le=100, description="AI-computed qualification score (0-100).")
    urgency: str = Field(description="LOW | MEDIUM | HIGH | CRITICAL")
    extracted_budget_estimate: str = Field(
        description="Inferred budget tier: startup, small_business, medium_enterprise, large_enterprise."
    )
    ai_summary: str = Field(description="One-paragraph AI analysis of the inquiry.")
    processed_at: str = Field(description="ISO 8601 UTC timestamp of processing completion.")


class ErrorResponse(BaseModel):
    """Structured error envelope returned on 4xx/5xx responses."""

    model_config = {"json_schema_extra": {"examples": [
        {
            "error_code": "LLM_PROVIDER_FAILURE",
            "message": "The AI analysis provider failed to deliver a valid structured response.",
            "details": {},
        }
    ]}}

    error_code: str = Field(description="Machine-readable error identifier.")
    message: str = Field(description="Human-readable error description.")
    details: dict[str, str] = Field(
        default_factory=dict,
        description="Optional key-value pairs with additional context.",
    )

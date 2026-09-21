from pydantic import BaseModel, EmailStr, Field


class IngestLeadRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    contact_email: EmailStr
    inquiry_text: str = Field(min_length=10, max_length=10_000)
    source: str = Field(min_length=1, max_length=100)


class IngestLeadResponse(BaseModel):
    lead_id: str
    status: str
    score: int
    urgency: str
    extracted_budget_estimate: str
    ai_summary: str
    processed_at: str


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: dict[str, str] = Field(default_factory=dict)

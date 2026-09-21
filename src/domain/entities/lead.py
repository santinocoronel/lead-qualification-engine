from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.errors.domain_errors import LeadValidationError
from src.domain.value_objects.email import Email
from src.domain.value_objects.enums import QualificationStatus, UrgencyLevel
from src.domain.value_objects.lead_score import LeadScore


@dataclass(slots=True)
class Lead:
    company_name: str
    contact_email: Email
    inquiry_text: str
    source: str
    score: LeadScore
    urgency: UrgencyLevel
    status: QualificationStatus
    ai_summary: str
    extracted_budget_estimate: str
    lead_id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.company_name.strip():
            raise LeadValidationError("company_name must not be empty")
        if not self.inquiry_text.strip():
            raise LeadValidationError("inquiry_text must not be empty")
        if not self.source.strip():
            raise LeadValidationError("source must not be empty")

    @staticmethod
    def determine_status(score: int) -> QualificationStatus:
        if score >= 70:
            return QualificationStatus.QUALIFIED
        if score >= 40:
            return QualificationStatus.REVIEW_NEEDED
        return QualificationStatus.DISQUALIFIED

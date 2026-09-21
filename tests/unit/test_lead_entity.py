import pytest

from src.domain.entities.lead import Lead
from src.domain.errors.domain_errors import LeadValidationError
from src.domain.value_objects.email import Email
from src.domain.value_objects.enums import QualificationStatus, UrgencyLevel
from src.domain.value_objects.lead_score import LeadScore


def _make_lead(**overrides: object) -> Lead:
    defaults: dict[str, object] = {
        "company_name": "Acme Corp",
        "contact_email": Email("test@acme.com"),
        "inquiry_text": "We need automation.",
        "source": "web_form",
        "score": LeadScore(85),
        "urgency": UrgencyLevel.HIGH,
        "status": QualificationStatus.QUALIFIED,
        "ai_summary": "Needs automation pipeline.",
        "extracted_budget_estimate": "medium_enterprise",
    }
    defaults.update(overrides)
    return Lead(**defaults)  # type: ignore[arg-type]


class TestLead:
    def test_create_valid_lead(self) -> None:
        lead = _make_lead()
        assert lead.company_name == "Acme Corp"
        assert lead.score.value == 85
        assert lead.lead_id is not None

    def test_empty_company_name_raises(self) -> None:
        with pytest.raises(LeadValidationError, match="company_name"):
            _make_lead(company_name="  ")

    def test_empty_inquiry_raises(self) -> None:
        with pytest.raises(LeadValidationError, match="inquiry_text"):
            _make_lead(inquiry_text="")

    def test_empty_source_raises(self) -> None:
        with pytest.raises(LeadValidationError, match="source"):
            _make_lead(source="   ")


class TestDetermineStatus:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (100, QualificationStatus.QUALIFIED),
            (70, QualificationStatus.QUALIFIED),
            (69, QualificationStatus.REVIEW_NEEDED),
            (40, QualificationStatus.REVIEW_NEEDED),
            (39, QualificationStatus.DISQUALIFIED),
            (0, QualificationStatus.DISQUALIFIED),
        ],
    )
    def test_status_thresholds(self, score: int, expected: QualificationStatus) -> None:
        assert Lead.determine_status(score) == expected

import pytest

from src.domain.errors.domain_errors import InvalidEmailError, InvalidLeadScoreError
from src.domain.value_objects.email import Email
from src.domain.value_objects.lead_score import LeadScore


class TestEmail:
    def test_valid_email(self) -> None:
        email = Email("User@Example.COM")
        assert email.value == "user@example.com"

    def test_email_with_whitespace(self) -> None:
        email = Email("  test@domain.org  ")
        assert email.value == "test@domain.org"

    @pytest.mark.parametrize("invalid", ["", "noatsign", "@nodomain", "user@", "a@b"])
    def test_invalid_email_raises(self, invalid: str) -> None:
        with pytest.raises(InvalidEmailError):
            Email(invalid)

    def test_email_str(self) -> None:
        assert str(Email("me@test.com")) == "me@test.com"


class TestLeadScore:
    def test_valid_score(self) -> None:
        assert LeadScore(0).value == 0
        assert LeadScore(100).value == 100
        assert LeadScore(55).value == 55

    @pytest.mark.parametrize("bad_score", [-1, 101, -100, 999])
    def test_invalid_score_raises(self, bad_score: int) -> None:
        with pytest.raises(InvalidLeadScoreError):
            LeadScore(bad_score)

    def test_int_conversion(self) -> None:
        assert int(LeadScore(42)) == 42

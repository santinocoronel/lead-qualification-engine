class DomainError(Exception):
    def __init__(self, message: str, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class InvalidEmailError(DomainError):
    def __init__(self, email: str) -> None:
        super().__init__(
            message=f"Invalid email format: '{email}'",
            error_code="INVALID_EMAIL",
        )


class InvalidLeadScoreError(DomainError):
    def __init__(self, score: int) -> None:
        super().__init__(
            message=f"Lead score must be between 0 and 100, got {score}",
            error_code="INVALID_LEAD_SCORE",
        )


class LeadValidationError(DomainError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            message=f"Lead validation failed: {detail}",
            error_code="LEAD_VALIDATION_ERROR",
        )


class LLMAnalysisError(DomainError):
    """Base for all LLM-related failures."""

    def __init__(self, message: str, error_code: str = "LLM_ANALYSIS_ERROR") -> None:
        super().__init__(message=message, error_code=error_code)


class LLMProviderError(LLMAnalysisError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            message=f"The AI analysis provider failed: {detail}",
            error_code="LLM_PROVIDER_FAILURE",
        )


class LLMResponseValidationError(LLMAnalysisError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            message=f"The AI response did not conform to the expected schema: {detail}",
            error_code="LLM_RESPONSE_VALIDATION_ERROR",
        )

from __future__ import annotations

import asyncio
from enum import StrEnum

import structlog
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from src.domain.errors.domain_errors import LLMProviderError, LLMResponseValidationError
from src.domain.ports.llm_analyzer_port import LLMAnalysisResult, LLMAnalyzerPort
from src.domain.value_objects.enums import UrgencyLevel
from src.infrastructure.config.settings import Settings

logger = structlog.get_logger(__name__)


class _UrgencySchema(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class _LeadAnalysisSchema(BaseModel):
    score: int = Field(ge=0, le=100, description="Lead qualification score from 0 to 100")
    urgency: _UrgencySchema = Field(description="Urgency level of the inquiry")
    budget_estimate: str = Field(description="Budget tier: startup, small_business, medium_enterprise, large_enterprise")
    summary: str = Field(max_length=500, description="Concise analysis summary")


_SYSTEM_PROMPT = """\
You are a B2B lead qualification analyst. Analyze the incoming inquiry and produce a structured assessment.

Scoring criteria (0-100):
- Budget signals (explicit mention of budget, company size indicators): 0-30 points
- Urgency signals (deadlines, immediate need, time pressure): 0-25 points
- Technical fit (clear technical requirements, scale indicators): 0-25 points
- Intent clarity (specific ask vs vague browsing): 0-20 points

Budget estimate tiers:
- startup: early-stage, limited budget, <10 employees
- small_business: established but constrained, 10-50 employees
- medium_enterprise: dedicated budget, 50-500 employees
- large_enterprise: significant budget, 500+ employees

Be precise and data-driven. Base the score strictly on evidence in the inquiry text.\
"""

_RETRYABLE_ERRORS = (
    ConnectionError,
    TimeoutError,
    asyncio.TimeoutError,
)


class GeminiLeadAnalyzer(LLMAnalyzerPort):
    def __init__(self, settings: Settings) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model
        self._timeout = settings.llm_timeout_seconds
        self._max_retries = settings.llm_max_retries
        self._retry_base_delay = settings.llm_retry_base_delay

    async def analyze_lead(
        self,
        company_name: str,
        inquiry_text: str,
        source: str,
    ) -> LLMAnalysisResult:
        user_prompt = (
            f"Company: {company_name}\n"
            f"Source: {source}\n"
            f"Inquiry:\n{inquiry_text}"
        )

        raw_text = await self._call_with_retry(user_prompt)
        return self._parse_response(raw_text)

    async def _call_with_retry(self, prompt: str) -> str:
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    self._client.aio.models.generate_content(
                        model=self._model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=_SYSTEM_PROMPT,
                            response_mime_type="application/json",
                            response_schema=_LeadAnalysisSchema,
                            temperature=0.1,
                        ),
                    ),
                    timeout=self._timeout,
                )

                if not response.text:
                    raise LLMProviderError(detail="Empty response from Gemini")

                logger.info(
                    "gemini_call_succeeded",
                    attempt=attempt,
                    model=self._model,
                )
                return response.text

            except _RETRYABLE_ERRORS as exc:
                last_error = exc
                delay = self._retry_base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "gemini_transient_failure",
                    attempt=attempt,
                    max_retries=self._max_retries,
                    retry_delay_seconds=delay,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(delay)

            except LLMProviderError:
                raise

            except Exception as exc:
                logger.error(
                    "gemini_non_retryable_failure",
                    attempt=attempt,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                raise LLMProviderError(detail=str(exc)) from exc

        raise LLMProviderError(
            detail=f"All {self._max_retries} retry attempts exhausted. Last error: {last_error}"
        ) from last_error

    def _parse_response(self, raw_text: str) -> LLMAnalysisResult:
        try:
            parsed = _LeadAnalysisSchema.model_validate_json(raw_text)
        except Exception as exc:
            logger.error(
                "gemini_response_validation_failed",
                raw_response=raw_text[:500],
                error=str(exc),
            )
            raise LLMResponseValidationError(detail=str(exc)) from exc

        return LLMAnalysisResult(
            score=parsed.score,
            urgency=UrgencyLevel(parsed.urgency.value),
            budget_estimate=parsed.budget_estimate,
            summary=parsed.summary,
        )

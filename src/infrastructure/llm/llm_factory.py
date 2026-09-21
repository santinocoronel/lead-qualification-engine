from __future__ import annotations

import json

import httpx
import structlog

from src.domain.errors.domain_errors import LLMProviderError, LLMResponseValidationError
from src.domain.ports.llm_analyzer_port import LLMAnalysisResult, LLMAnalyzerPort
from src.domain.value_objects.enums import UrgencyLevel
from src.infrastructure.config.settings import Settings
from src.infrastructure.llm.gemini_analyzer import GeminiLeadAnalyzer

logger = structlog.get_logger(__name__)

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

Respond ONLY with a JSON object containing:
- "score": integer 0-100
- "urgency": one of "LOW", "MEDIUM", "HIGH", "CRITICAL"
- "budget_estimate": one of "startup", "small_business", "medium_enterprise", "large_enterprise"
- "summary": string max 500 chars

Be precise and data-driven. Base the score strictly on evidence in the inquiry text.\
"""


def create_analyzer(
    settings: Settings,
    provider: str | None = None,
    api_key: str | None = None,
) -> LLMAnalyzerPort:
    if not provider or not api_key:
        return GeminiLeadAnalyzer(settings)

    match provider:
        case "gemini":
            return _BYOKGeminiAnalyzer(api_key, settings)
        case "openai":
            return _OpenAIAnalyzer(api_key, settings)
        case "anthropic":
            return _AnthropicAnalyzer(api_key, settings)
        case _:
            raise LLMProviderError(f"Unsupported LLM provider: {provider}")


def _parse_json_response(raw: str) -> LLMAnalysisResult:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMResponseValidationError(f"Invalid JSON from LLM: {exc}") from exc

    try:
        return LLMAnalysisResult(
            score=int(data["score"]),
            urgency=UrgencyLevel(data["urgency"]),
            budget_estimate=str(data["budget_estimate"]),
            summary=str(data["summary"])[:500],
        )
    except (KeyError, ValueError) as exc:
        raise LLMResponseValidationError(f"Missing or invalid field: {exc}") from exc


class _BYOKGeminiAnalyzer(LLMAnalyzerPort):
    def __init__(self, api_key: str, settings: Settings) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = settings.gemini_model
        self._timeout = settings.llm_timeout_seconds

    async def analyze_lead(
        self,
        company_name: str,
        inquiry_text: str,
        source: str,
    ) -> LLMAnalysisResult:
        import asyncio

        from google.genai import types

        user_prompt = f"Company: {company_name}\nSource: {source}\nInquiry:\n{inquiry_text}"
        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self._model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=_SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                ),
                timeout=self._timeout,
            )
            if not response.text:
                raise LLMProviderError(detail="Empty response from Gemini (BYOK)")
            return _parse_json_response(response.text)
        except (LLMProviderError, LLMResponseValidationError):
            raise
        except Exception as exc:
            raise LLMProviderError(detail=f"Gemini BYOK error: {exc}") from exc


class _OpenAIAnalyzer(LLMAnalyzerPort):
    def __init__(self, api_key: str, settings: Settings) -> None:
        self._api_key = api_key
        self._timeout = settings.llm_timeout_seconds

    async def analyze_lead(
        self,
        company_name: str,
        inquiry_text: str,
        source: str,
    ) -> LLMAnalysisResult:
        user_prompt = f"Company: {company_name}\nSource: {source}\nInquiry:\n{inquiry_text}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": "gpt-4o",
                        "messages": [
                            {"role": "system", "content": _SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.1,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return _parse_json_response(content)
        except (LLMProviderError, LLMResponseValidationError):
            raise
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(detail=f"OpenAI API error: {exc.response.status_code}") from exc
        except Exception as exc:
            raise LLMProviderError(detail=f"OpenAI error: {exc}") from exc


class _AnthropicAnalyzer(LLMAnalyzerPort):
    def __init__(self, api_key: str, settings: Settings) -> None:
        self._api_key = api_key
        self._timeout = settings.llm_timeout_seconds

    async def analyze_lead(
        self,
        company_name: str,
        inquiry_text: str,
        source: str,
    ) -> LLMAnalysisResult:
        user_prompt = f"Company: {company_name}\nSource: {source}\nInquiry:\n{inquiry_text}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 1024,
                        "system": _SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": user_prompt}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["content"][0]["text"]
                return _parse_json_response(content)
        except (LLMProviderError, LLMResponseValidationError):
            raise
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                detail=f"Anthropic API error: {exc.response.status_code}"
            ) from exc
        except Exception as exc:
            raise LLMProviderError(detail=f"Anthropic error: {exc}") from exc

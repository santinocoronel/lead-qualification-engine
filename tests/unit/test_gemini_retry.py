from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.errors.domain_errors import LLMProviderError, LLMResponseValidationError
from src.infrastructure.llm.gemini_analyzer import GeminiLeadAnalyzer


def _make_settings() -> MagicMock:
    s = MagicMock()
    s.gemini_api_key = "test-key"
    s.gemini_model = "gemini-3.8-flash"
    s.llm_timeout_seconds = 5
    s.llm_max_retries = 3
    s.llm_retry_base_delay = 0.01
    return s


_VALID_JSON = '{"score": 85, "urgency": "HIGH", "budget_estimate": "medium_enterprise", "summary": "Needs automation."}'


class TestGeminiRetry:
    @patch("src.infrastructure.llm.gemini_analyzer.genai")
    async def test_succeeds_on_first_try(self, mock_genai: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.text = _VALID_JSON
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_genai.Client.return_value = mock_client

        analyzer = GeminiLeadAnalyzer(_make_settings())
        result = await analyzer.analyze_lead("Acme", "Need automation for PDFs", "web")

        assert result.score == 85
        assert result.urgency.value == "HIGH"
        assert mock_client.aio.models.generate_content.await_count == 1

    @patch("src.infrastructure.llm.gemini_analyzer.genai")
    async def test_retries_on_transient_failure_then_succeeds(self, mock_genai: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.text = _VALID_JSON
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=[ConnectionError("reset"), TimeoutError("slow"), mock_response]
        )
        mock_genai.Client.return_value = mock_client

        analyzer = GeminiLeadAnalyzer(_make_settings())
        result = await analyzer.analyze_lead("Acme", "Need automation", "web")

        assert result.score == 85
        assert mock_client.aio.models.generate_content.await_count == 3

    @patch("src.infrastructure.llm.gemini_analyzer.genai")
    async def test_exhausts_retries_raises_provider_error(self, mock_genai: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=ConnectionError("down")
        )
        mock_genai.Client.return_value = mock_client

        analyzer = GeminiLeadAnalyzer(_make_settings())
        with pytest.raises(LLMProviderError, match="retry attempts exhausted"):
            await analyzer.analyze_lead("Acme", "Need automation", "web")

        assert mock_client.aio.models.generate_content.await_count == 3

    @patch("src.infrastructure.llm.gemini_analyzer.genai")
    async def test_non_retryable_error_fails_immediately(self, mock_genai: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=ValueError("bad config")
        )
        mock_genai.Client.return_value = mock_client

        analyzer = GeminiLeadAnalyzer(_make_settings())
        with pytest.raises(LLMProviderError, match="bad config"):
            await analyzer.analyze_lead("Acme", "Need automation", "web")

        assert mock_client.aio.models.generate_content.await_count == 1

    @patch("src.infrastructure.llm.gemini_analyzer.genai")
    async def test_malformed_json_raises_validation_error(self, mock_genai: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.text = '{"score": "not_a_number"}'
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_genai.Client.return_value = mock_client

        analyzer = GeminiLeadAnalyzer(_make_settings())
        with pytest.raises(LLMResponseValidationError):
            await analyzer.analyze_lead("Acme", "Need automation", "web")

    @patch("src.infrastructure.llm.gemini_analyzer.genai")
    async def test_empty_response_raises_provider_error(self, mock_genai: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.text = ""
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_genai.Client.return_value = mock_client

        analyzer = GeminiLeadAnalyzer(_make_settings())
        with pytest.raises(LLMProviderError, match="Empty response"):
            await analyzer.analyze_lead("Acme", "Need automation", "web")

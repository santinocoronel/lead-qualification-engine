from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from src.infrastructure.crypto.fernet_utils import decrypt_value, encrypt_value
from src.infrastructure.llm.llm_factory import _parse_json_response, create_analyzer
from src.domain.errors.domain_errors import LLMProviderError, LLMResponseValidationError


class TestFernetEncryption:
    def setup_method(self) -> None:
        self.key = Fernet.generate_key().decode()

    def test_encrypt_decrypt_roundtrip(self) -> None:
        original = "sk-test-openai-key-12345"
        encrypted = encrypt_value(original, self.key)
        assert encrypted != original
        assert decrypt_value(encrypted, self.key) == original

    def test_decrypt_with_wrong_key_raises(self) -> None:
        encrypted = encrypt_value("secret", self.key)
        wrong_key = Fernet.generate_key().decode()
        with pytest.raises(ValueError, match="Failed to decrypt"):
            decrypt_value(encrypted, wrong_key)

    def test_decrypt_corrupted_data_raises(self) -> None:
        with pytest.raises(ValueError, match="Failed to decrypt"):
            decrypt_value("not-valid-fernet-data", self.key)


class TestParseJsonResponse:
    def test_valid_response(self) -> None:
        raw = '{"score": 85, "urgency": "HIGH", "budget_estimate": "medium_enterprise", "summary": "Good lead"}'
        result = _parse_json_response(raw)
        assert result.score == 85
        assert result.urgency.value == "HIGH"
        assert result.budget_estimate == "medium_enterprise"

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(LLMResponseValidationError, match="Invalid JSON"):
            _parse_json_response("not json at all")

    def test_missing_field_raises(self) -> None:
        raw = '{"score": 85, "urgency": "HIGH"}'
        with pytest.raises(LLMResponseValidationError, match="Missing or invalid"):
            _parse_json_response(raw)


class TestCreateAnalyzer:
    def test_no_provider_returns_gemini(self) -> None:
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.gemini_api_key = "fake-key"
        settings.gemini_model = "gemini-2.5-flash"
        settings.llm_timeout_seconds = 30
        settings.llm_max_retries = 3
        settings.llm_retry_base_delay = 1.0

        analyzer = create_analyzer(settings, provider=None, api_key=None)
        assert type(analyzer).__name__ == "GeminiLeadAnalyzer"

    def test_unsupported_provider_raises(self) -> None:
        from unittest.mock import MagicMock

        settings = MagicMock()
        with pytest.raises(LLMProviderError, match="Unsupported"):
            create_analyzer(settings, provider="unknown", api_key="key")

    def test_openai_provider_creates_analyzer(self) -> None:
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.llm_timeout_seconds = 30
        analyzer = create_analyzer(settings, provider="openai", api_key="sk-test")
        assert type(analyzer).__name__ == "_OpenAIAnalyzer"

    def test_anthropic_provider_creates_analyzer(self) -> None:
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.llm_timeout_seconds = 30
        analyzer = create_analyzer(settings, provider="anthropic", api_key="sk-ant-test")
        assert type(analyzer).__name__ == "_AnthropicAnalyzer"

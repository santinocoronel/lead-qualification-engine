from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import structlog

from src.domain.errors.domain_errors import LLMProviderError

logger = structlog.get_logger(__name__)

_STREAM_TIMEOUT = 120


@dataclass(frozen=True, slots=True)
class _ProviderSpec:
    base_url: str
    model: str
    auth_header: str = "Authorization"
    auth_prefix: str = "Bearer"
    extra_headers: dict[str, str] | None = None
    max_tokens: int | None = None


_OPENAI_COMPAT_PROVIDERS: dict[str, _ProviderSpec] = {
    "openai": _ProviderSpec(
        base_url="https://api.openai.com/v1/chat/completions",
        model="gpt-4o",
    ),
    "deepseek": _ProviderSpec(
        base_url="https://api.deepseek.com/chat/completions",
        model="deepseek-coder",
    ),
    "mistral": _ProviderSpec(
        base_url="https://api.mistral.ai/v1/chat/completions",
        model="codestral-latest",
    ),
}


async def stream_code_generation(
    provider: str,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
) -> AsyncIterator[str]:
    if provider == "gemini":
        async for chunk in _stream_gemini(api_key, system_prompt, user_prompt):
            yield chunk
        return

    if provider == "anthropic":
        async for chunk in _stream_anthropic(api_key, system_prompt, user_prompt):
            yield chunk
        return

    spec = _OPENAI_COMPAT_PROVIDERS.get(provider)
    if not spec:
        raise LLMProviderError(f"Unsupported provider: {provider}")

    async for chunk in _stream_openai_compat(spec, api_key, system_prompt, user_prompt):
        yield chunk


async def _stream_openai_compat(
    spec: _ProviderSpec,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
) -> AsyncIterator[str]:
    headers = {spec.auth_header: f"{spec.auth_prefix} {api_key}"}
    if spec.extra_headers:
        headers.update(spec.extra_headers)

    body: dict[str, object] = {
        "model": spec.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": True,
        "temperature": 0.2,
    }
    if spec.max_tokens:
        body["max_tokens"] = spec.max_tokens

    try:
        async with httpx.AsyncClient(timeout=_STREAM_TIMEOUT) as client:
            async with client.stream("POST", spec.base_url, headers=headers, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        break
                    try:
                        delta = json.loads(payload)["choices"][0].get("delta", {})
                        if text := delta.get("content", ""):
                            yield text
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
    except httpx.HTTPStatusError as exc:
        raise LLMProviderError(f"{spec.model} API error: {exc.response.status_code}") from exc
    except LLMProviderError:
        raise
    except Exception as exc:
        logger.error("openai_compat_stream_error", provider=spec.model, error=str(exc))
        raise LLMProviderError(f"{spec.model} streaming failed: {exc}") from exc


async def _stream_gemini(
    api_key: str, system_prompt: str, user_prompt: str
) -> AsyncIterator[str]:
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content_stream(
            model="gemini-2.0-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2,
            ),
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text
    except LLMProviderError:
        raise
    except Exception as exc:
        logger.error("gemini_stream_error", error=str(exc))
        raise LLMProviderError(f"Gemini streaming error: {exc}") from exc


async def _stream_anthropic(
    api_key: str, system_prompt: str, user_prompt: str
) -> AsyncIterator[str]:
    try:
        async with httpx.AsyncClient(timeout=_STREAM_TIMEOUT) as client:
            async with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 8192,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "stream": True,
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        parsed = json.loads(line[6:])
                        if parsed.get("type") == "content_block_delta":
                            if text := parsed.get("delta", {}).get("text", ""):
                                yield text
                    except (json.JSONDecodeError, KeyError):
                        continue
    except httpx.HTTPStatusError as exc:
        raise LLMProviderError(f"Anthropic API error: {exc.response.status_code}") from exc
    except LLMProviderError:
        raise
    except Exception as exc:
        logger.error("anthropic_stream_error", error=str(exc))
        raise LLMProviderError(f"Anthropic streaming error: {exc}") from exc

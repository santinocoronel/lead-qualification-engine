from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import structlog

from src.domain.errors.domain_errors import LLMProviderError

logger = structlog.get_logger(__name__)


async def stream_code_generation(
    provider: str,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
) -> AsyncIterator[str]:
    match provider:
        case "gemini":
            async for chunk in _stream_gemini(api_key, system_prompt, user_prompt):
                yield chunk
        case "openai":
            async for chunk in _stream_openai(api_key, system_prompt, user_prompt):
                yield chunk
        case "anthropic":
            async for chunk in _stream_anthropic(api_key, system_prompt, user_prompt):
                yield chunk
        case "deepseek":
            async for chunk in _stream_deepseek(api_key, system_prompt, user_prompt):
                yield chunk
        case "mistral":
            async for chunk in _stream_mistral(api_key, system_prompt, user_prompt):
                yield chunk
        case _:
            raise LLMProviderError(f"Unsupported provider: {provider}")


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


async def _stream_openai(
    api_key: str, system_prompt: str, user_prompt: str
) -> AsyncIterator[str]:
    import json

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": True,
                    "temperature": 0.2,
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        parsed = json.loads(data)
                        delta = parsed["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
    except httpx.HTTPStatusError as exc:
        raise LLMProviderError(f"OpenAI API error: {exc.response.status_code}") from exc
    except LLMProviderError:
        raise
    except Exception as exc:
        logger.error("openai_stream_error", error=str(exc))
        raise LLMProviderError(f"OpenAI streaming error: {exc}") from exc


async def _stream_anthropic(
    api_key: str, system_prompt: str, user_prompt: str
) -> AsyncIterator[str]:
    import json

    try:
        async with httpx.AsyncClient(timeout=120) as client:
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
                            text = parsed.get("delta", {}).get("text", "")
                            if text:
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


async def _stream_deepseek(
    api_key: str, system_prompt: str, user_prompt: str
) -> AsyncIterator[str]:
    import json

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "deepseek-coder",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": True,
                    "temperature": 0.2,
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        parsed = json.loads(data)
                        delta = parsed["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
    except httpx.HTTPStatusError as exc:
        raise LLMProviderError(f"DeepSeek API error: {exc.response.status_code}") from exc
    except LLMProviderError:
        raise
    except Exception as exc:
        logger.error("deepseek_stream_error", error=str(exc))
        raise LLMProviderError(f"DeepSeek streaming error: {exc}") from exc


async def _stream_mistral(
    api_key: str, system_prompt: str, user_prompt: str
) -> AsyncIterator[str]:
    import json

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                "https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "codestral-latest",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": True,
                    "temperature": 0.2,
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        parsed = json.loads(data)
                        delta = parsed["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
    except httpx.HTTPStatusError as exc:
        raise LLMProviderError(f"Mistral API error: {exc.response.status_code}") from exc
    except LLMProviderError:
        raise
    except Exception as exc:
        logger.error("mistral_stream_error", error=str(exc))
        raise LLMProviderError(f"Mistral streaming error: {exc}") from exc

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from src.application.services.prompt_assembler import assemble_system_prompt
from src.domain.entities.project_context import (
    ARCHITECTURE_RULES,
    SUPPORTED_FRAMEWORKS,
    SUPPORTED_LANGUAGES,
    ProjectContext,
)
from src.domain.value_objects.enums import LLMProvider
from src.infrastructure.llm.streaming_factory import stream_code_generation

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Code Generation"])


class ContextPayload(BaseModel):
    language: str = Field(examples=["python_3.12"])
    framework: str = Field(examples=["fastapi"])
    rules: list[str] = Field(default_factory=list, examples=[["clean_architecture", "strict_typing"]])


class GenerateCodeRequest(BaseModel):
    provider: str = Field(examples=["gemini"])
    api_key: str = Field(min_length=1)
    context: ContextPayload
    task_description: str = Field(min_length=1, max_length=10000)


class ConfigResponse(BaseModel):
    languages: dict[str, str]
    frameworks: dict[str, list[str]]
    rules: dict[str, str]
    providers: list[str]


@router.get(
    "/config",
    response_model=ConfigResponse,
    summary="Get available languages, frameworks, rules and providers",
)
async def get_config() -> ConfigResponse:
    return ConfigResponse(
        languages=SUPPORTED_LANGUAGES,
        frameworks=SUPPORTED_FRAMEWORKS,
        rules=ARCHITECTURE_RULES,
        providers=[p.value for p in LLMProvider],
    )


@router.post(
    "/generate-code",
    summary="Generate code with AI using project context (SSE streaming)",
    response_model=None,
)
async def generate_code(request: Request, payload: GenerateCodeRequest) -> StreamingResponse | JSONResponse:
    valid_providers = {p.value for p in LLMProvider}
    if payload.provider not in valid_providers:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": f"Invalid provider. Must be one of: {', '.join(valid_providers)}"},
        )

    try:
        context = ProjectContext(
            language=payload.context.language,
            framework=payload.context.framework,
            rules=payload.context.rules,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )

    system_prompt = assemble_system_prompt(context)

    logger.info(
        "code_generation_started",
        provider=payload.provider,
        language=context.language,
        framework=context.framework,
        rules=context.rules,
    )

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for chunk in stream_code_generation(
                provider=payload.provider,
                api_key=payload.api_key,
                system_prompt=system_prompt,
                user_prompt=payload.task_description,
            ):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            logger.error("code_generation_error", error=str(exc))
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

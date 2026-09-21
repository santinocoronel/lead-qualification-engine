from __future__ import annotations

import json
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from src.application.services.prompt_assembler import (
    TASK_TEMPLATES,
    assemble_review_prompt,
    assemble_system_prompt,
)
from src.domain.entities.project_context import (
    ARCHITECTURE_RULES,
    SUPPORTED_FRAMEWORKS,
    SUPPORTED_LANGUAGES,
    ProjectContext,
)
from src.domain.value_objects.enums import LLMProvider
from src.infrastructure.llm.streaming_factory import PROVIDER_MODELS, stream_code_generation

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Code Generation"])

_VALID_PROVIDERS = frozenset(p.value for p in LLMProvider)

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class ContextPayload(BaseModel):
    language: str = Field(examples=["python_3.12"])
    framework: str = Field(examples=["fastapi"])
    rules: list[str] = Field(default_factory=list, examples=[["clean_architecture", "strict_typing"]])


class GenerateCodeRequest(BaseModel):
    provider: str = Field(examples=["gemini"])
    model: str | None = Field(default=None, examples=["gemini-2.5-flash"])
    api_key: str = Field(min_length=1)
    context: ContextPayload
    task_description: str = Field(min_length=1, max_length=10000)


class ReviewCodeRequest(BaseModel):
    provider: str = Field(examples=["gemini"])
    model: str | None = Field(default=None, examples=["gemini-2.5-flash"])
    api_key: str = Field(min_length=1)
    context: ContextPayload
    code: str = Field(min_length=1, max_length=50000)


class TemplateInfo(BaseModel):
    name: str
    description: str
    prompt: str
    category: str


class ModelInfo(BaseModel):
    id: str
    name: str


class ConfigResponse(BaseModel):
    languages: dict[str, str]
    frameworks: dict[str, list[str]]
    rules: dict[str, str]
    providers: list[str]
    models: dict[str, list[ModelInfo]]
    templates: dict[str, TemplateInfo]


def _validate_provider(provider: str) -> JSONResponse | None:
    if provider not in _VALID_PROVIDERS:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": f"Invalid provider. Must be one of: {', '.join(sorted(_VALID_PROVIDERS))}"},
        )
    return None


def _build_context(ctx: ContextPayload) -> ProjectContext | JSONResponse:
    try:
        return ProjectContext(language=ctx.language, framework=ctx.framework, rules=ctx.rules)
    except ValueError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )


def _sse_response(
    provider: str,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    log_event: str,
    model: str | None = None,
) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        try:
            async for chunk in stream_code_generation(
                provider=provider, api_key=api_key,
                system_prompt=system_prompt, user_prompt=user_prompt,
                model=model,
            ):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            logger.error(log_event, error=str(exc))
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.get(
    "/config",
    response_model=ConfigResponse,
    summary="Get available languages, frameworks, rules, providers and templates",
)
async def get_config() -> ConfigResponse:
    return ConfigResponse(
        languages=SUPPORTED_LANGUAGES,
        frameworks=SUPPORTED_FRAMEWORKS,
        rules=ARCHITECTURE_RULES,
        providers=sorted(_VALID_PROVIDERS),
        models={
            p: [ModelInfo(id=mid, name=mname) for mid, mname in ms]
            for p, ms in PROVIDER_MODELS.items()
        },
        templates={k: TemplateInfo(**v) for k, v in TASK_TEMPLATES.items()},
    )


@router.post(
    "/generate-code",
    summary="Generate code with AI using project context (SSE streaming)",
    response_model=None,
)
async def generate_code(request: Request, payload: GenerateCodeRequest) -> StreamingResponse | JSONResponse:
    if err := _validate_provider(payload.provider):
        return err

    context = _build_context(payload.context)
    if isinstance(context, JSONResponse):
        return context

    logger.info(
        "code_generation_started",
        provider=payload.provider,
        language=context.language,
        framework=context.framework,
        rules=context.rules,
    )

    return _sse_response(
        provider=payload.provider,
        api_key=payload.api_key,
        system_prompt=assemble_system_prompt(context),
        user_prompt=payload.task_description,
        log_event="code_generation_error",
        model=payload.model,
    )


@router.post(
    "/review-code",
    summary="Review code against architecture rules (SSE streaming)",
    response_model=None,
)
async def review_code(request: Request, payload: ReviewCodeRequest) -> StreamingResponse | JSONResponse:
    if err := _validate_provider(payload.provider):
        return err

    context = _build_context(payload.context)
    if isinstance(context, JSONResponse):
        return context

    logger.info(
        "code_review_started",
        provider=payload.provider,
        language=context.language,
        code_length=len(payload.code),
    )

    return _sse_response(
        provider=payload.provider,
        api_key=payload.api_key,
        system_prompt=assemble_review_prompt(context),
        user_prompt=f"Review this code:\n\n{payload.code}",
        log_event="code_review_error",
        model=payload.model,
    )

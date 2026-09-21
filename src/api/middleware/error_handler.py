from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

import structlog

from src.domain.errors.domain_errors import (
    DomainError,
    InvalidEmailError,
    InvalidLeadScoreError,
    LeadValidationError,
    LLMProviderError,
    LLMResponseValidationError,
)

logger = structlog.get_logger(__name__)

_DOMAIN_TO_HTTP: dict[type[DomainError], int] = {
    InvalidEmailError: 422,
    InvalidLeadScoreError: 422,
    LeadValidationError: status.HTTP_400_BAD_REQUEST,
    LLMProviderError: status.HTTP_502_BAD_GATEWAY,
    LLMResponseValidationError: status.HTTP_502_BAD_GATEWAY,
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        http_status = _DOMAIN_TO_HTTP.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.warning(
            "domain_error",
            error_code=exc.error_code,
            message=str(exc),
            http_status=http_status,
        )
        return JSONResponse(
            status_code=http_status,
            content={
                "error_code": exc.error_code,
                "message": str(exc),
                "details": {},
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
                "details": {},
            },
        )

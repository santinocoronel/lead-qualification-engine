from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from slowapi.errors import RateLimitExceeded

from src.api.middleware.error_handler import register_error_handlers
from src.api.middleware.rate_limiter import limiter, rate_limit_exceeded_handler
from src.api.v1.auth_router import router as auth_router
from src.api.v1.billing_router import router as billing_router
from src.api.v1.health_router import router as health_router
from src.api.v1.leads_router import router as leads_router
from src.infrastructure.email.smtp_adapter import ConsoleEmailAdapter, SMTPEmailAdapter
from src.infrastructure.config.settings import Settings
from src.infrastructure.persistence.database import async_session_factory, create_engine


def _configure_logging(settings: Settings) -> None:
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_format == "console":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

_OPENAPI_DESCRIPTION = """\
## Overview

AI-powered **B2B lead qualification engine** that processes inbound prospect inquiries,
scores them across four dimensions (budget, urgency, technical fit, intent clarity)
using Google Gemini with structured JSON output, and persists the result transactionally
in PostgreSQL.

## Architecture

Built on **Clean Architecture / Hexagonal** principles:

| Layer | Responsibility |
|-------|---------------|
| **Domain** | Entities, Value Objects, Ports (interfaces), typed errors |
| **Application** | Use Case orchestration — zero infrastructure imports |
| **Infrastructure** | SQLAlchemy 2.0 async adapter, Gemini LLM client with retry |
| **API** | FastAPI controllers, Pydantic v2 DTOs, error mapping |

## Resilience

- **Retry with exponential backoff** on transient LLM failures (configurable attempts + base delay)
- **Structured JSON logging** with per-request `X-Request-ID` tracing
- **Typed domain errors** mapped to semantic HTTP status codes (400 / 422 / 502 / 500)

## Authentication & Quota

All scoring endpoints require an **API key** via the `X-API-Key` header.
Keys are SHA-256 hashed and validated against the `clients` table in PostgreSQL.
Each request verifies:

1. **Key validity** — exists in DB (with 30s in-memory TTL cache)
2. **Subscription status** — must be `ACTIVE`
3. **Monthly quota** — `monthly_requests_used < monthly_requests_limit`

Returns `401` (missing key), `403` (invalid/inactive), or `429` (quota exhausted).

## Rate Limiting

Per-endpoint rate limiting via **slowapi** (default 60 req/min per IP).
Returns `429 Too Many Requests` with `Retry-After` header.

## Billing (Merchant of Record)

**Lemon Squeezy** webhook integration at `POST /api/v1/billing/webhook` handles
subscription lifecycle events with instant activation:

| Event | Action |
|-------|--------|
| `subscription_created` / `order_created` | Set `ACTIVE`, assign plan tier + quota, reset usage |
| `subscription_updated` | Upgrade/downgrade plan tier + quota |
| `subscription_expired` | Set `INACTIVE` |
| `subscription_payment_failed` | Set `PAST_DUE` |
| `subscription_cancelled` | Set `CANCELED` |
| `subscription_resumed` | Set `ACTIVE` |

Plans: **FREE** (100 req/mo), **PRO** (5,000 req/mo), **AGENCY** (25,000 req/mo).
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger = structlog.get_logger("lifecycle")
    settings: Settings = app.state.settings
    _configure_logging(settings)
    engine = create_engine(settings)
    app.state.engine = engine
    app.state.session_factory = async_session_factory(engine)

    if settings.smtp_host:
        app.state.email_adapter = SMTPEmailAdapter(settings)
    else:
        app.state.email_adapter = ConsoleEmailAdapter()

    logger.info("application_started", version=settings.app_version)
    yield
    await engine.dispose()
    logger.info("application_stopped")


def create_app() -> FastAPI:
    settings = Settings()  # type: ignore[call-arg]

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=_OPENAPI_DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {
                "name": "Lead qualification",
                "description": "Ingest, score and persist B2B leads via AI analysis.",
            },
            {
                "name": "health",
                "description": "Liveness and readiness probes for orchestrators and load balancers.",
            },
            {
                "name": "Authentication",
                "description": "Client registration, JWT login, and password management.",
            },
            {
                "name": "Billing",
                "description": "Lemon Squeezy webhook integration for subscription lifecycle management.",
            },
        ],
        contact={"name": "Lead Engine API Support"},
        license_info={"name": "MIT", "identifier": "MIT"},
    )

    app.state.settings = settings
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: object) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response: Response = await call_next(request)  # type: ignore[misc]
        response.headers["X-Request-ID"] = request_id
        return response

    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(leads_router)
    app.include_router(billing_router)

    return app

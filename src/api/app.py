from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from src.api.middleware.error_handler import register_error_handlers
from src.api.middleware.rate_limiter import limiter, rate_limit_exceeded_handler
from src.api.v1.auth_router import router as auth_router
from src.api.v1.billing_router import router as billing_router
from src.api.v1.generate_router import router as generate_router
from src.api.v1.health_router import router as health_router
from src.api.v1.leads_router import router as leads_router
from src.infrastructure.config.settings import Settings
from src.infrastructure.email.resend_adapter import ResendEmailAdapter
from src.infrastructure.email.smtp_adapter import ConsoleEmailAdapter, SMTPEmailAdapter
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
## AI Context Engine

Intelligent middleware between developers and LLMs. Configure your tech stack,
define architecture rules, and generate production-ready code — streamed in
real time via SSE.

### Core Capabilities

| Feature | Detail |
|---------|--------|
| **Code Generation** | 20 languages, 50+ frameworks, 5 AI providers |
| **Code Review** | Severity scoring against 20 architecture rules |
| **Task Templates** | 12 battle-tested prompts for common patterns |
| **BYOK** | Bring your own API key — never stored, per-request only |
| **SSE Streaming** | Token-by-token output as it's generated |

### Architecture

Clean Architecture / Hexagonal — Domain → Application → Infrastructure → API.

- **Async throughout** — SQLAlchemy 2.0 async with asyncpg on PostgreSQL
- **Structured logging** — JSON with per-request `X-Request-ID` correlation
- **Typed errors** — domain errors mapped to semantic HTTP status codes

### Authentication

JWT-based login (`POST /api/v1/auth/login`) for the dashboard.
API key via `X-API-Key` header for programmatic access.
Keys are SHA-256 hashed; subscriptions and monthly quotas enforced per-request.

### Plans

| Tier | Generations/mo | Price |
|------|---------------|-------|
| Free | 100 | $0 |
| Pro | 5,000 | $49 |
| Agency | 25,000 | $199 |
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger = structlog.get_logger("lifecycle")
    settings: Settings = app.state.settings
    _configure_logging(settings)

    engine = create_engine(settings)
    app.state.engine = engine
    app.state.session_factory = async_session_factory(engine)

    if settings.resend_api_key:
        app.state.email_adapter = ResendEmailAdapter(
            api_key=settings.resend_api_key,
            from_email=settings.resend_from_email,
        )
    elif settings.smtp_host:
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
                "name": "Code Generation",
                "description": "AI-powered code generation and review with project context, architecture rules, and SSE streaming.",
            },
            {
                "name": "Authentication",
                "description": "Client registration, JWT login, BYOK configuration, and password management.",
            },
            {
                "name": "Billing",
                "description": "PayPro Global and Lemon Squeezy webhook receivers for subscription lifecycle.",
            },
            {
                "name": "Lead qualification",
                "description": "Ingest and score B2B leads via AI analysis.",
            },
            {
                "name": "health",
                "description": "Liveness and readiness probes.",
            },
        ],
        contact={"name": "AI Context Engine", "url": settings.base_url},
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
    async def security_headers(request: Request, call_next: object) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response: Response = await call_next(request)  # type: ignore[misc]
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(leads_router)
    app.include_router(generate_router)
    app.include_router(billing_router)

    static_dir = Path(__file__).resolve().parent.parent.parent / "static"
    if static_dir.is_dir():
        @app.get("/", include_in_schema=False)
        async def landing_page() -> FileResponse:
            return FileResponse(static_dir / "index.html")

        @app.get("/dashboard.html", include_in_schema=False)
        async def dashboard_page() -> FileResponse:
            return FileResponse(static_dir / "dashboard.html")

        @app.get("/checkout.html", include_in_schema=False)
        async def checkout_page() -> FileResponse:
            return FileResponse(static_dir / "checkout.html")

        @app.get("/terms.html", include_in_schema=False)
        async def terms_page() -> FileResponse:
            return FileResponse(static_dir / "terms.html")

        @app.get("/privacy.html", include_in_schema=False)
        async def privacy_page() -> FileResponse:
            return FileResponse(static_dir / "privacy.html")

        @app.get("/refunds.html", include_in_schema=False)
        async def refunds_page() -> FileResponse:
            return FileResponse(static_dir / "refunds.html")

        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app

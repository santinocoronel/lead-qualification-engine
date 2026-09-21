from __future__ import annotations

from src.domain.entities.project_context import (
    ARCHITECTURE_RULES,
    SUPPORTED_LANGUAGES,
    ProjectContext,
)


TASK_TEMPLATES: dict[str, dict[str, str]] = {
    "auth_jwt": {
        "name": "JWT Authentication Endpoint",
        "description": "User registration + login with JWT tokens, bcrypt password hashing, and refresh token rotation.",
        "prompt": "Create a complete JWT authentication system with: user registration endpoint (email + password with validation), login endpoint returning access + refresh tokens, refresh token rotation endpoint, password hashing with bcrypt, token expiration handling, and a protected route decorator/middleware that validates the JWT.",
        "category": "auth",
    },
    "crud_repository": {
        "name": "CRUD Repository + Endpoints",
        "description": "Full CRUD operations with repository pattern, validation, pagination, and error handling.",
        "prompt": "Create a complete CRUD module for a 'Product' entity with: domain entity with id/name/description/price/created_at fields, repository port (interface) with create/get_by_id/list_all/update/delete methods, an in-memory or database adapter implementing the repository, use case layer orchestrating business logic, API endpoints for all CRUD operations with input validation, pagination for list endpoint (page + page_size), and proper error handling with typed domain errors.",
        "category": "backend",
    },
    "websocket_chat": {
        "name": "WebSocket Real-Time Chat",
        "description": "WebSocket server with rooms, broadcasting, connection management, and message history.",
        "prompt": "Build a WebSocket-based real-time chat system with: connection manager handling connect/disconnect events, room-based messaging (join/leave rooms), message broadcasting to all users in a room, connection heartbeat/ping-pong, message history stored in memory (last 100 messages per room), typed message schemas (join, leave, message, system), and a simple REST endpoint to list active rooms with user counts.",
        "category": "realtime",
    },
    "file_upload": {
        "name": "File Upload Service",
        "description": "Multipart file upload with validation, virus scanning interface, S3-compatible storage, and thumbnails.",
        "prompt": "Create a file upload service with: multipart upload endpoint accepting images/documents, file validation (max size, allowed MIME types, magic byte verification), storage adapter interface (port) with a local filesystem implementation, unique filename generation with original extension preserved, upload metadata stored (original name, size, content type, upload timestamp, uploader ID), list uploads endpoint with pagination, download endpoint with proper Content-Type headers, and a delete endpoint.",
        "category": "backend",
    },
    "rate_limiter": {
        "name": "Rate Limiter Middleware",
        "description": "Token bucket rate limiter with per-client limits, Redis-compatible backend, and 429 responses.",
        "prompt": "Implement a rate limiting middleware with: token bucket algorithm (configurable rate + burst), per-client identification via API key or IP, configurable limits per endpoint, Redis-compatible backend adapter (with in-memory fallback), proper 429 Too Many Requests response with Retry-After header, rate limit headers on every response (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset), and a decorator/middleware that's easy to apply to any route.",
        "category": "infra",
    },
    "email_service": {
        "name": "Email Notification Service",
        "description": "Templated email service with queue, retry logic, SMTP adapter, and event-driven triggers.",
        "prompt": "Build an email notification service with: email template engine (welcome, password reset, invoice), SMTP adapter with TLS support, email queue with retry logic (3 attempts with exponential backoff), event-driven triggers (user_registered -> welcome email, password_reset_requested -> reset email), email logging with delivery status tracking, HTML + plain text multipart emails, and a port/adapter pattern so the SMTP implementation can be swapped.",
        "category": "backend",
    },
    "database_migration": {
        "name": "Database Migration System",
        "description": "Schema migration runner with up/down migrations, version tracking, and rollback support.",
        "prompt": "Create a database migration system with: migration file structure (timestamp_description with up/down SQL), migration runner that executes pending migrations in order, migration version tracking table, rollback support (run down migrations), migration status command showing applied/pending, transaction wrapping per migration (rollback on failure), and a CLI-style interface or API endpoint to run/rollback/status.",
        "category": "infra",
    },
    "caching_layer": {
        "name": "Caching Layer with TTL",
        "description": "Multi-level cache with TTL, invalidation, cache-aside pattern, and Redis-compatible adapter.",
        "prompt": "Implement a caching layer with: cache port (interface) with get/set/delete/invalidate_pattern methods, TTL support per cache entry, in-memory LRU cache adapter, Redis-compatible adapter structure, cache-aside pattern helper (check cache -> miss -> compute -> store -> return), cache key builder with namespace prefixes, bulk invalidation by pattern/tag, and a decorator that caches function results automatically based on arguments.",
        "category": "infra",
    },
    "testing_suite": {
        "name": "Testing Suite Setup",
        "description": "Complete test infrastructure with fixtures, factories, mocks, and integration test patterns.",
        "prompt": "Set up a complete testing infrastructure with: test configuration and fixtures, entity factory (creates test data with sensible defaults and overrides), fake/stub implementations for all repository ports, unit tests for a sample use case (at least 5 test cases covering happy path, validation errors, not found, duplicate, and edge cases), integration test pattern for an API endpoint with a test client, test database setup/teardown helpers, and assertion helpers for common domain patterns.",
        "category": "testing",
    },
    "ci_pipeline": {
        "name": "CI/CD Pipeline Config",
        "description": "GitHub Actions workflow with lint, test, build, Docker push, and deploy stages.",
        "prompt": "Create a complete CI/CD pipeline configuration (GitHub Actions) with: lint stage (code formatter + linter), test stage (unit + integration with coverage report), build stage (compile/bundle), Docker build and push to registry stage, deploy stage (with environment variables and secrets), caching for dependencies between runs, parallel jobs where possible, environment-based deployment (staging on PR merge, production on release tag), and status badges for README.",
        "category": "devops",
    },
    "api_gateway": {
        "name": "API Gateway Pattern",
        "description": "API gateway with routing, auth middleware, rate limiting, request logging, and health aggregation.",
        "prompt": "Build an API gateway pattern with: route registration and request forwarding to backend services, authentication middleware (JWT validation), rate limiting per route, request/response logging with correlation IDs, circuit breaker for downstream service calls (open after 5 failures, half-open after 30s), health check aggregation endpoint that pings all downstream services, request timeout configuration per route, and CORS handling.",
        "category": "arch",
    },
    "event_bus": {
        "name": "Event Bus / Pub-Sub",
        "description": "In-process event bus with typed events, async handlers, error isolation, and dead letter queue.",
        "prompt": "Implement an in-process event bus / pub-sub system with: typed event classes (base Event with timestamp + event_id), event handler registration (subscribe by event type), async event publishing and handling, handler error isolation (one handler failure doesn't block others), event history/log (last N events), dead letter queue for failed events, handler retry with configurable attempts, and an example showing domain events (UserRegistered, OrderPlaced) with their handlers.",
        "category": "arch",
    },
}


def _build_rules_block(context: ProjectContext) -> str:
    if not context.rules:
        return ""
    rules_lines = []
    for i, rule_key in enumerate(context.rules, 1):
        desc = ARCHITECTURE_RULES[rule_key]
        rules_lines.append(f"{i}. **{rule_key.replace('_', ' ').title()}**: {desc}")
    return "\n".join(rules_lines)


def assemble_system_prompt(context: ProjectContext) -> str:
    lang_label = SUPPORTED_LANGUAGES[context.language]
    fw_label = context.framework if context.framework != "none" else "no framework"
    rules_block = _build_rules_block(context)

    return f"""\
You are an expert senior software engineer and code architect.

## Target Stack
- **Language**: {lang_label}
- **Framework**: {fw_label}

## Mandatory Architecture Rules
{rules_block if rules_block else "No specific architecture rules selected. Use industry best practices."}

## Output Requirements
1. Write production-ready, complete code — no placeholders, no TODOs, no "implement here" comments.
2. Use idiomatic patterns for {lang_label} and {fw_label}.
3. Include all necessary imports and type annotations.
4. If multiple files are needed, clearly separate them with `# === filename.ext ===` headers.
5. Add brief inline comments ONLY when the logic is non-obvious.
6. Handle errors appropriately according to the rules above.
7. Do NOT explain the code after writing it — the code speaks for itself.
8. Do NOT wrap code in markdown code fences — output raw code directly."""


def assemble_review_prompt(context: ProjectContext) -> str:
    lang_label = SUPPORTED_LANGUAGES[context.language]
    fw_label = context.framework if context.framework != "none" else "no framework"
    rules_block = _build_rules_block(context)

    return f"""\
You are a strict senior code reviewer and software architect.

## Target Stack
- **Language**: {lang_label}
- **Framework**: {fw_label}

## Architecture Rules to Enforce
{rules_block if rules_block else "No specific architecture rules selected. Review against industry best practices."}

## Review Instructions
Analyze the submitted code against the architecture rules above. For each issue found:

1. **Severity**: CRITICAL / WARNING / INFO
2. **Location**: file and line/section where the issue is
3. **Rule violated**: which architecture rule is broken
4. **Problem**: what is wrong (be specific)
5. **Fix**: concrete code showing how to fix it (not vague advice)

After listing issues, provide:
- **Score**: 0-100 overall quality score
- **Summary**: 2-3 sentence assessment
- **Top 3 improvements**: the highest-impact changes to make

Be strict but constructive. If the code is good, say so. Do NOT wrap output in markdown code fences."""

from __future__ import annotations

from dataclasses import dataclass, field


SUPPORTED_LANGUAGES: dict[str, str] = {
    "python_3.12": "Python 3.12+",
    "python_3.14": "Python 3.14+",
    "typescript_5": "TypeScript 5.x",
    "javascript_es2024": "JavaScript ES2024",
    "go_1.22": "Go 1.22+",
    "rust_2024": "Rust 2024 Edition",
    "java_21": "Java 21 LTS",
    "java_17": "Java 17 LTS",
    "csharp_12": "C# 12 / .NET 8",
    "cpp_23": "C++ 23",
    "cpp_20": "C++ 20",
    "kotlin_2": "Kotlin 2.x",
    "swift_5": "Swift 5.10+",
    "php_8": "PHP 8.3+",
    "ruby_3": "Ruby 3.3+",
    "dart_3": "Dart 3.x",
    "scala_3": "Scala 3.x",
    "elixir_1": "Elixir 1.16+",
    "zig_0": "Zig 0.13+",
    "lua_5": "Lua 5.4",
}

SUPPORTED_FRAMEWORKS: dict[str, list[str]] = {
    "python_3.12": ["fastapi", "django", "flask", "litestar", "sanic", "none"],
    "python_3.14": ["fastapi", "django", "flask", "litestar", "sanic", "none"],
    "typescript_5": ["nextjs", "express", "nestjs", "hono", "astro", "nuxt", "svelte-kit", "none"],
    "javascript_es2024": ["express", "fastify", "hono", "koa", "none"],
    "go_1.22": ["gin", "fiber", "echo", "chi", "none"],
    "rust_2024": ["actix-web", "axum", "rocket", "warp", "none"],
    "java_21": ["spring-boot", "quarkus", "micronaut", "vert.x", "none"],
    "java_17": ["spring-boot", "quarkus", "micronaut", "vert.x", "none"],
    "csharp_12": ["aspnet-core", "minimal-api", "blazor", "none"],
    "cpp_23": ["crow", "drogon", "pistache", "none"],
    "cpp_20": ["crow", "drogon", "pistache", "none"],
    "kotlin_2": ["ktor", "spring-boot", "http4k", "none"],
    "swift_5": ["vapor", "hummingbird", "none"],
    "php_8": ["laravel", "symfony", "slim", "none"],
    "ruby_3": ["rails", "sinatra", "hanami", "none"],
    "dart_3": ["flutter", "shelf", "dart_frog", "none"],
    "scala_3": ["zio-http", "play", "http4s", "none"],
    "elixir_1": ["phoenix", "plug", "none"],
    "zig_0": ["zap", "none"],
    "lua_5": ["lapis", "none"],
}

ARCHITECTURE_RULES: dict[str, str] = {
    "clean_architecture": (
        "Follow Clean Architecture / Hexagonal Architecture strictly. "
        "Separate Domain (entities, value objects, ports), Application (use cases), "
        "Infrastructure (adapters, persistence, external services), and API (controllers, DTOs) layers. "
        "Domain MUST NOT import from infrastructure or API layers."
    ),
    "strict_typing": (
        "Use strict static typing everywhere. All function signatures must have full type annotations. "
        "No implicit Any types. Use generics where appropriate. Prefer typed dataclasses or models."
    ),
    "solid_principles": (
        "Apply SOLID principles rigorously: Single Responsibility per class/module, "
        "Open/Closed via abstractions, Liskov Substitution in hierarchies, "
        "Interface Segregation with focused ports, Dependency Inversion via constructor injection."
    ),
    "error_handling": (
        "Implement typed domain errors. Never use generic exceptions. "
        "Map domain errors to HTTP status codes at the API boundary. "
        "Use Result types or explicit error returns instead of exception-based flow where possible."
    ),
    "repository_pattern": (
        "Use the Repository Pattern for all data persistence. Define abstract repository ports in Domain. "
        "Implement concrete adapters in Infrastructure. Use Unit of Work for transactional boundaries."
    ),
    "dto_validation": (
        "Use Pydantic v2 BaseModel for all API DTOs. Separate input/output schemas. "
        "Validate at the boundary, pass domain entities internally. No ORM models in API responses."
    ),
    "dependency_injection": (
        "Wire all dependencies via constructor injection. Use a composition root or DI container. "
        "No service locator pattern. No global mutable state."
    ),
    "testing_strategy": (
        "Design for testability: all external dependencies behind ports/interfaces. "
        "Unit tests for domain logic (no I/O). Integration tests for adapters. "
        "Use fakes/stubs, not mocks, for domain-layer tests."
    ),
    "security_best_practices": (
        "Sanitize all user input. Parameterize SQL queries. Hash secrets with bcrypt/argon2. "
        "Use HTTPS only. Apply CORS, rate limiting, and CSRF protections. "
        "Never log sensitive data. Follow OWASP Top 10."
    ),
    "async_patterns": (
        "Use async/await for all I/O operations. No blocking calls in async code. "
        "Use connection pools for databases and HTTP clients. "
        "Handle cancellation and timeouts explicitly."
    ),
    "cqrs_pattern": (
        "Separate Command (write) and Query (read) responsibilities into distinct models and handlers. "
        "Commands mutate state and return void or an ID. Queries return data and never mutate. "
        "Use separate read/write repositories if persistence allows."
    ),
    "event_driven": (
        "Use domain events to decouple bounded contexts. Publish events after state changes. "
        "Subscribe to events for side effects (notifications, projections, auditing). "
        "Events are immutable records of something that happened."
    ),
    "api_versioning": (
        "Version all public APIs via URL prefix (/api/v1/) or header-based versioning. "
        "Never break existing API contracts. Use deprecation headers for sunset endpoints. "
        "Maintain backward compatibility or provide migration paths."
    ),
    "logging_observability": (
        "Use structured JSON logging with correlation/request IDs for distributed tracing. "
        "Log at appropriate levels: DEBUG for development, INFO for business events, "
        "WARN for recoverable issues, ERROR for failures. Emit OpenTelemetry-compatible spans."
    ),
    "database_patterns": (
        "Use migrations for all schema changes (Alembic, Flyway, etc). Never modify schema manually. "
        "Index columns used in WHERE/JOIN. Use database transactions for data consistency. "
        "Apply optimistic locking for concurrent writes. Avoid N+1 queries."
    ),
    "microservices_patterns": (
        "Design services around business capabilities with clear bounded contexts. "
        "Use API gateways for cross-cutting concerns. Implement circuit breakers for inter-service calls. "
        "Use saga pattern for distributed transactions. Each service owns its data store."
    ),
    "functional_patterns": (
        "Prefer pure functions and immutable data structures. Use higher-order functions, "
        "map/filter/reduce over imperative loops. Avoid side effects in business logic. "
        "Use monadic error handling (Option/Result/Either) where the language supports it."
    ),
    "container_ready": (
        "Design for containerized deployment. Use environment variables for configuration. "
        "Implement health check endpoints (/health, /ready). Support graceful shutdown. "
        "Log to stdout/stderr. Build multi-stage Docker images for minimal footprint."
    ),
    "rate_limiting_throttling": (
        "Implement rate limiting per client/IP at the API gateway or middleware layer. "
        "Use token bucket or sliding window algorithms. Return 429 with Retry-After header. "
        "Apply backpressure for internal service-to-service communication."
    ),
    "documentation_first": (
        "Generate OpenAPI/Swagger specs from code annotations. Document all public endpoints "
        "with request/response examples. Use doc comments on public interfaces. "
        "Maintain a README with setup, architecture decisions, and deployment instructions."
    ),
}


@dataclass(frozen=True)
class ProjectContext:
    language: str
    framework: str
    rules: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {self.language}")
        valid_frameworks = SUPPORTED_FRAMEWORKS.get(self.language, [])
        if self.framework not in valid_frameworks:
            raise ValueError(
                f"Framework '{self.framework}' not supported for {self.language}. "
                f"Valid: {valid_frameworks}"
            )
        for rule in self.rules:
            if rule not in ARCHITECTURE_RULES:
                raise ValueError(f"Unknown rule: {rule}")

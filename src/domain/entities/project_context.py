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
    "csharp_12": "C# 12 / .NET 8",
}

SUPPORTED_FRAMEWORKS: dict[str, list[str]] = {
    "python_3.12": ["fastapi", "django", "flask", "none"],
    "python_3.14": ["fastapi", "django", "flask", "none"],
    "typescript_5": ["nextjs", "express", "nestjs", "none"],
    "javascript_es2024": ["express", "fastify", "none"],
    "go_1.22": ["gin", "fiber", "echo", "none"],
    "rust_2024": ["actix-web", "axum", "rocket", "none"],
    "java_21": ["spring-boot", "quarkus", "none"],
    "csharp_12": ["aspnet-core", "minimal-api", "none"],
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

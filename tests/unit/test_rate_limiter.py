from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded

from src.api.middleware.rate_limiter import limiter, rate_limit_exceeded_handler


def _build_app() -> FastAPI:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]

    @app.get("/test")
    @limiter.limit("3/minute")
    async def test_route(request: Request) -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    return app


class TestRateLimiter:
    def test_allows_requests_under_limit(self) -> None:
        client = TestClient(_build_app())
        response = client.get("/test")
        assert response.status_code == 200

    def test_blocks_after_limit_exceeded(self) -> None:
        client = TestClient(_build_app())
        for _ in range(3):
            client.get("/test")
        response = client.get("/test")
        assert response.status_code == 429
        assert response.json()["error_code"] == "RATE_LIMIT_EXCEEDED"
        assert "Retry-After" in response.headers

    def test_unlimited_endpoints_bypass(self) -> None:
        client = TestClient(_build_app())
        for _ in range(10):
            response = client.get("/ping")
            assert response.status_code == 200

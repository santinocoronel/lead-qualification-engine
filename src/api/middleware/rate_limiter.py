from __future__ import annotations

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse


def _key_func(request: Request) -> str:
    return get_remote_address(request) or "unknown"


limiter = Limiter(key_func=_key_func)


def rate_limit_exceeded_handler(_request: Request, exc: RateLimitExceeded) -> Response:
    return JSONResponse(
        status_code=429,
        content={
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": f"Rate limit exceeded: {exc.detail}",
            "details": {},
        },
        headers={"Retry-After": "60"},
    )

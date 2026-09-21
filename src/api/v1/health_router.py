from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import text

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    database: str


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    db_status = "disconnected"
    try:
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception:
        db_status = "unreachable"

    overall = "healthy" if db_status == "connected" else "degraded"

    return HealthResponse(
        status=overall,
        version=request.app.state.settings.app_version,
        timestamp=datetime.now(UTC).isoformat(),
        database=db_status,
    )


@router.get("/ping")
async def ping() -> dict[str, str]:
    return {"status": "ok"}

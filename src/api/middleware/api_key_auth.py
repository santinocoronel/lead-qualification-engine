from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass

import structlog
from fastapi import Request, Security, status
from fastapi.exceptions import HTTPException
from fastapi.security import APIKeyHeader
from sqlalchemy import select, update

from src.infrastructure.persistence.client_model import ClientModel

logger = structlog.get_logger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

_CACHE_TTL_SECONDS = 30.0


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


@dataclass
class _CacheEntry:
    client: ClientModel
    expires_at: float


_client_cache: dict[str, _CacheEntry] = {}


def _get_cached(key_hash: str) -> ClientModel | None:
    entry = _client_cache.get(key_hash)
    if entry and time.monotonic() < entry.expires_at:
        return entry.client
    if entry:
        del _client_cache[key_hash]
    return None


def _set_cached(key_hash: str, client: ClientModel) -> None:
    _client_cache[key_hash] = _CacheEntry(
        client=client,
        expires_at=time.monotonic() + _CACHE_TTL_SECONDS,
    )


def invalidate_cache(key_hash: str | None = None) -> None:
    if key_hash:
        _client_cache.pop(key_hash, None)
    else:
        _client_cache.clear()


async def require_api_key(
    request: Request,
    api_key: str | None = Security(_api_key_header),
) -> ClientModel:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
        )

    key_hash = hash_api_key(api_key)

    client = _get_cached(key_hash)
    if not client:
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            result = await session.execute(
                select(ClientModel).where(ClientModel.api_key_hash == key_hash)
            )
            client = result.scalar_one_or_none()

        if not client:
            logger.warning("auth_failed_unknown_key", key_prefix=api_key[:8])
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key.",
            )

        _set_cached(key_hash, client)

    if client.subscription_status != "ACTIVE":
        logger.warning(
            "auth_failed_inactive_subscription",
            owner_email=client.owner_email,
            status=client.subscription_status,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Subscription is {client.subscription_status}. Activate your plan to continue.",
        )

    is_byok = bool(client.encrypted_api_key and client.custom_llm_provider)

    if not is_byok:
        if client.monthly_requests_used >= client.monthly_requests_limit:
            logger.warning(
                "monthly_quota_exceeded",
                owner_email=client.owner_email,
                plan=client.plan_tier,
                used=client.monthly_requests_used,
                limit=client.monthly_requests_limit,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Monthly quota exhausted ({client.monthly_requests_used}/{client.monthly_requests_limit}). "
                    f"Upgrade your plan for higher limits."
                ),
            )

        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(ClientModel)
                    .where(ClientModel.id == client.id)
                    .values(monthly_requests_used=ClientModel.monthly_requests_used + 1)
                )

        client.monthly_requests_used += 1

        email_adapter = getattr(request.app.state, "email_adapter", None)
        if email_adapter:
            from src.application.services.usage_alert_service import check_usage_alerts

            asyncio.create_task(
                check_usage_alerts(client, session_factory, email_adapter)
            )

    structlog.contextvars.bind_contextvars(
        client_email=client.owner_email,
        plan_tier=client.plan_tier,
        requests_used=client.monthly_requests_used,
        requests_limit=client.monthly_requests_limit,
        byok=is_byok,
    )
    return client

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass

import structlog
from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, update

from src.api.middleware.api_key_auth import invalidate_cache
from src.domain.value_objects.enums import PlanTier, SubscriptionStatus
from src.infrastructure.persistence.client_model import ClientModel

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["Billing"])


@dataclass(frozen=True)
class _PlanConfig:
    tier: PlanTier
    monthly_limit: int


_VARIANT_TO_PLAN: dict[str, _PlanConfig] = {
    "Free": _PlanConfig(tier=PlanTier.FREE, monthly_limit=100),
    "Pro": _PlanConfig(tier=PlanTier.PRO, monthly_limit=5000),
    "Agency": _PlanConfig(tier=PlanTier.AGENCY, monthly_limit=25000),
}

_DEFAULT_PLAN = _PlanConfig(tier=PlanTier.FREE, monthly_limit=100)


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Lemon Squeezy webhook receiver",
    description=(
        "Receives Lemon Squeezy webhook events for subscription lifecycle management. "
        "Validates the HMAC-SHA256 signature via `X-Signature`, then dispatches events "
        "to instantly activate, upgrade, suspend or revoke client subscriptions in PostgreSQL. "
        "Handles: `subscription_created`, `order_created`, `subscription_updated`, "
        "`subscription_expired`, `subscription_payment_failed`, `subscription_cancelled`, "
        "`subscription_resumed`."
    ),
    responses={
        200: {"description": "Webhook processed successfully."},
        400: {"description": "Invalid signature or malformed payload."},
    },
)
async def lemonsqueezy_webhook(
    request: Request,
    x_signature: str | None = Header(None, alias="X-Signature"),
) -> JSONResponse:
    settings = request.app.state.settings
    webhook_secret = settings.lemonsqueezy_webhook_secret

    if not webhook_secret:
        logger.error("lemonsqueezy_webhook_secret_not_configured")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Webhook not configured."},
        )

    body = await request.body()

    if not x_signature or not _verify_signature(body, x_signature, webhook_secret):
        logger.warning("lemonsqueezy_webhook_invalid_signature")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Invalid signature."},
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Invalid JSON payload."},
        )

    event_name = payload.get("meta", {}).get("event_name", "unknown")
    custom_data = payload.get("meta", {}).get("custom_data", {})
    attributes = payload.get("data", {}).get("attributes", {})
    customer_id = str(payload.get("data", {}).get("id", ""))
    user_email = custom_data.get("user_email", attributes.get("user_email", ""))

    logger.info(
        "lemonsqueezy_webhook_received",
        event_name=event_name,
        customer_id=customer_id,
        user_email=user_email,
    )

    match event_name:
        case "subscription_created" | "order_created":
            variant = attributes.get("variant_name", "Free")
            plan_cfg = _VARIANT_TO_PLAN.get(variant, _DEFAULT_PLAN)
            await _activate_subscription(
                request.app.state.session_factory, user_email, customer_id, plan_cfg
            )

        case "subscription_updated":
            variant = attributes.get("variant_name", "Free")
            plan_cfg = _VARIANT_TO_PLAN.get(variant, _DEFAULT_PLAN)
            await _update_plan(request.app.state.session_factory, user_email, plan_cfg)

        case "subscription_expired":
            await _set_status(request.app.state.session_factory, user_email, SubscriptionStatus.INACTIVE)

        case "subscription_payment_failed":
            await _set_status(request.app.state.session_factory, user_email, SubscriptionStatus.PAST_DUE)

        case "subscription_cancelled":
            await _set_status(request.app.state.session_factory, user_email, SubscriptionStatus.CANCELED)

        case "subscription_resumed":
            await _reactivate(request.app.state.session_factory, user_email)

        case _:
            logger.debug("lemonsqueezy_unhandled_event", event_name=event_name)

    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok"})


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    computed = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


async def _activate_subscription(
    session_factory: object,
    user_email: str,
    customer_id: str,
    plan_cfg: _PlanConfig,
) -> None:
    async with session_factory() as session:  # type: ignore[operator]
        async with session.begin():
            result = await session.execute(
                select(ClientModel).where(ClientModel.owner_email == user_email)
            )
            client = result.scalar_one_or_none()

            if client:
                await session.execute(
                    update(ClientModel)
                    .where(ClientModel.id == client.id)
                    .values(
                        subscription_status=SubscriptionStatus.ACTIVE,
                        plan_tier=plan_cfg.tier,
                        monthly_requests_limit=plan_cfg.monthly_limit,
                        monthly_requests_used=0,
                        lemon_squeezy_customer_id=customer_id,
                        alert_80_sent_at=None,
                        alert_95_sent_at=None,
                    )
                )
                invalidate_cache(client.api_key_hash)
                logger.info(
                    "subscription_activated",
                    user_email=user_email,
                    plan=plan_cfg.tier,
                    monthly_limit=plan_cfg.monthly_limit,
                )
            else:
                logger.warning("client_not_found_for_activation", user_email=user_email)


async def _update_plan(
    session_factory: object,
    user_email: str,
    plan_cfg: _PlanConfig,
) -> None:
    async with session_factory() as session:  # type: ignore[operator]
        async with session.begin():
            result = await session.execute(
                select(ClientModel).where(ClientModel.owner_email == user_email)
            )
            client = result.scalar_one_or_none()

            if client:
                await session.execute(
                    update(ClientModel)
                    .where(ClientModel.id == client.id)
                    .values(
                        plan_tier=plan_cfg.tier,
                        monthly_requests_limit=plan_cfg.monthly_limit,
                    )
                )
                invalidate_cache(client.api_key_hash)
                logger.info(
                    "plan_updated",
                    user_email=user_email,
                    plan=plan_cfg.tier,
                    monthly_limit=plan_cfg.monthly_limit,
                )
            else:
                logger.warning("client_not_found_for_plan_update", user_email=user_email)


async def _set_status(
    session_factory: object,
    user_email: str,
    new_status: SubscriptionStatus,
) -> None:
    async with session_factory() as session:  # type: ignore[operator]
        async with session.begin():
            result = await session.execute(
                select(ClientModel).where(ClientModel.owner_email == user_email)
            )
            client = result.scalar_one_or_none()

            if client:
                await session.execute(
                    update(ClientModel)
                    .where(ClientModel.id == client.id)
                    .values(subscription_status=new_status)
                )
                invalidate_cache(client.api_key_hash)
                logger.info(
                    "subscription_status_changed",
                    user_email=user_email,
                    new_status=new_status,
                )
            else:
                logger.warning("client_not_found_for_status_change", user_email=user_email)


async def _reactivate(session_factory: object, user_email: str) -> None:
    async with session_factory() as session:  # type: ignore[operator]
        async with session.begin():
            result = await session.execute(
                select(ClientModel).where(ClientModel.owner_email == user_email)
            )
            client = result.scalar_one_or_none()

            if client:
                await session.execute(
                    update(ClientModel)
                    .where(ClientModel.id == client.id)
                    .values(subscription_status=SubscriptionStatus.ACTIVE)
                )
                invalidate_cache(client.api_key_hash)
                logger.info("subscription_reactivated", user_email=user_email)
            else:
                logger.warning("client_not_found_for_reactivation", user_email=user_email)

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, update

from src.api.middleware.api_key_auth import invalidate_cache
from src.domain.value_objects.enums import PlanTier, SubscriptionStatus
from src.infrastructure.email.templates import subscription_activated_email
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
                request.app.state.session_factory, user_email, customer_id, plan_cfg,
                email_adapter=request.app.state.email_adapter,
                base_url=request.app.state.settings.base_url,
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
    email_adapter: object | None = None,
    base_url: str = "",
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
                if email_adapter:
                    try:
                        subj, html = subscription_activated_email(
                            user_email, plan_cfg.tier.value.title(), plan_cfg.monthly_limit, base_url,
                        )
                        await email_adapter.send_email(user_email, subj, html)
                    except Exception as exc:
                        logger.warning("subscription_email_failed", error=str(exc))
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


_PAYPRO_PRODUCT_TO_PLAN: dict[str, _PlanConfig] = {
    "Pro": _PlanConfig(tier=PlanTier.PRO, monthly_limit=5000),
    "Agency": _PlanConfig(tier=PlanTier.AGENCY, monthly_limit=25000),
}


@router.post(
    "/paypro-webhook",
    status_code=status.HTTP_200_OK,
    summary="PayPro Global IPN webhook receiver",
    description=(
        "Receives PayPro Global IPN (Instant Payment Notification) events. "
        "Handles: CHARGE.COMPLETED, SUBSCRIPTION.ACTIVATED, SUBSCRIPTION.CANCELLED, "
        "SUBSCRIPTION.EXPIRED, CHARGE.REFUNDED, CHARGE.FAILED."
    ),
    responses={
        200: {"description": "Webhook processed successfully."},
        400: {"description": "Invalid payload or signature."},
    },
)
async def paypro_webhook(request: Request) -> JSONResponse:
    settings = request.app.state.settings
    body = await request.body()

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Invalid JSON payload."},
        )

    event_type = payload.get("event_type", payload.get("EventType", ""))
    order_data = payload.get("data", payload.get("IPN", {}))

    customer_email = (
        order_data.get("customer_email")
        or order_data.get("CustomerEmail")
        or order_data.get("BuyerEmail", "")
    )
    product_name = (
        order_data.get("product_name")
        or order_data.get("ProductName")
        or order_data.get("title", "")
    )
    order_id = str(
        order_data.get("order_id")
        or order_data.get("OrderId")
        or order_data.get("id", "")
    )

    logger.info(
        "paypro_webhook_received",
        event_type=event_type,
        customer_email=customer_email,
        product_name=product_name,
        order_id=order_id,
    )

    event_upper = event_type.upper().replace(".", "_").replace(" ", "_")

    if event_upper in (
        "CHARGE_COMPLETED", "SUBSCRIPTION_ACTIVATED", "ORDER_COMPLETED",
        "PAYMENT_COMPLETED", "SUBSCRIPTION_CREATED",
    ):
        plan_cfg = _DEFAULT_PLAN
        for key, cfg in _PAYPRO_PRODUCT_TO_PLAN.items():
            if key.lower() in product_name.lower():
                plan_cfg = cfg
                break
        await _activate_subscription(
            request.app.state.session_factory, customer_email, order_id, plan_cfg,
            email_adapter=request.app.state.email_adapter,
            base_url=request.app.state.settings.base_url,
        )

    elif event_upper in ("SUBSCRIPTION_CANCELLED", "SUBSCRIPTION_CANCELED"):
        await _set_status(
            request.app.state.session_factory, customer_email, SubscriptionStatus.CANCELED
        )

    elif event_upper in ("SUBSCRIPTION_EXPIRED", "SUBSCRIPTION_ENDED"):
        await _set_status(
            request.app.state.session_factory, customer_email, SubscriptionStatus.INACTIVE
        )

    elif event_upper in ("CHARGE_REFUNDED", "ORDER_REFUNDED"):
        await _set_status(
            request.app.state.session_factory, customer_email, SubscriptionStatus.INACTIVE
        )

    elif event_upper in ("CHARGE_FAILED", "PAYMENT_FAILED"):
        await _set_status(
            request.app.state.session_factory, customer_email, SubscriptionStatus.PAST_DUE
        )

    elif event_upper in ("SUBSCRIPTION_RESUMED", "SUBSCRIPTION_REACTIVATED"):
        await _reactivate(request.app.state.session_factory, customer_email)

    else:
        logger.debug("paypro_unhandled_event", event_type=event_type)

    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok"})


class CheckoutRequest(BaseModel):
    plan: str
    email: EmailStr


_PAYPRO_CHECKOUT_BASE = "https://store.payproglobal.com/checkout"


@router.post(
    "/checkout",
    status_code=status.HTTP_200_OK,
    summary="Generate PayPro Global checkout URL for a plan",
)
async def create_checkout(request: Request, payload: CheckoutRequest) -> JSONResponse:
    settings = request.app.state.settings

    product_ids: dict[str, str] = {
        "pro": settings.paypro_product_id_pro,
        "agency": settings.paypro_product_id_agency,
    }

    product_id = product_ids.get(payload.plan)
    if not product_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": f"Invalid plan: {payload.plan}. Must be 'pro' or 'agency'."},
        )

    if not product_id.strip():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Payment is not configured yet. Please contact support."},
        )

    checkout_params = urlencode({
        "products[1][id]": product_id,
        "billing-email": payload.email,
        "x-custom-user_email": payload.email,
        "currency": "USD",
        "page-template": "regular",
    })
    checkout_url = f"{_PAYPRO_CHECKOUT_BASE}?{checkout_params}"

    logger.info(
        "checkout_url_generated",
        plan=payload.plan,
        email=payload.email,
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"checkout_url": checkout_url},
    )

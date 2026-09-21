from __future__ import annotations

import asyncio
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
import structlog
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update

from src.api.middleware.api_key_auth import hash_api_key
from src.domain.value_objects.enums import PlanTier, SubscriptionStatus
from src.infrastructure.persistence.client_model import ClientModel

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterResponse(BaseModel):
    client_id: str
    email: str
    api_key: str
    plan_tier: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


def _create_access_token(data: dict[str, object], secret: str, algorithm: str, expire_minutes: int) -> str:
    payload = {**data, "exp": datetime.now(UTC) + timedelta(minutes=expire_minutes), "type": "access"}
    return jwt.encode(payload, secret, algorithm=algorithm)


def _create_refresh_token(data: dict[str, object], secret: str, algorithm: str, expire_days: int) -> str:
    payload = {**data, "exp": datetime.now(UTC) + timedelta(days=expire_days), "type": "refresh"}
    return jwt.encode(payload, secret, algorithm=algorithm)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterResponse,
    summary="Register a new client account",
)
async def register(request: Request, payload: RegisterRequest) -> RegisterResponse:
    session_factory = request.app.state.session_factory

    async with session_factory() as session:
        result = await session.execute(
            select(ClientModel).where(ClientModel.owner_email == payload.email)
        )
        if result.scalar_one_or_none():
            return JSONResponse(  # type: ignore[return-value]
                status_code=status.HTTP_409_CONFLICT,
                content={"detail": "Email already registered."},
            )

    raw_api_key = secrets.token_urlsafe(32)
    key_hash = hash_api_key(raw_api_key)
    password_hash = _hash_password(payload.password)

    import uuid

    client_id = uuid.uuid4()

    async with session_factory() as session:
        async with session.begin():
            client = ClientModel(
                id=client_id,
                owner_email=payload.email,
                api_key_hash=key_hash,
                password_hash=password_hash,
                plan_tier=PlanTier.FREE,
                subscription_status=SubscriptionStatus.ACTIVE,
                monthly_requests_limit=100,
                monthly_requests_used=0,
            )
            session.add(client)

    logger.info("client_registered", email=payload.email, plan=PlanTier.FREE)

    return RegisterResponse(
        client_id=str(client_id),
        email=payload.email,
        api_key=raw_api_key,
        plan_tier=PlanTier.FREE,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Authenticate and receive JWT tokens",
)
async def login(request: Request, payload: LoginRequest) -> LoginResponse | JSONResponse:
    settings = request.app.state.settings
    session_factory = request.app.state.session_factory

    async with session_factory() as session:
        result = await session.execute(
            select(ClientModel).where(ClientModel.owner_email == payload.email)
        )
        client = result.scalar_one_or_none()

    if not client or not client.password_hash or not _verify_password(payload.password, client.password_hash):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid email or password."},
        )

    token_data: dict[str, object] = {"sub": client.owner_email, "client_id": str(client.id)}

    access_token = _create_access_token(
        token_data,
        settings.jwt_secret_key,
        settings.jwt_algorithm,
        settings.jwt_access_token_expire_minutes,
    )
    refresh_token = _create_refresh_token(
        token_data,
        settings.jwt_secret_key,
        settings.jwt_algorithm,
        settings.jwt_refresh_token_expire_days,
    )

    logger.info("client_login", email=payload.email)

    return LoginResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password reset token",
)
async def forgot_password(request: Request, payload: ForgotPasswordRequest) -> MessageResponse:
    session_factory = request.app.state.session_factory
    email_adapter = request.app.state.email_adapter

    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    async with session_factory() as session:
        result = await session.execute(
            select(ClientModel).where(ClientModel.owner_email == payload.email)
        )
        client = result.scalar_one_or_none()

        if client:
            async with session.begin():
                await session.execute(
                    update(ClientModel)
                    .where(ClientModel.id == client.id)
                    .values(reset_token=reset_token, reset_token_expires_at=expires_at)
                )
            asyncio.create_task(
                email_adapter.send_email(
                    payload.email,
                    "Password Reset Request",
                    f"<p>Your password reset token: <strong>{reset_token}</strong></p>"
                    f"<p>This token expires in 1 hour.</p>",
                )
            )

    return MessageResponse(message="If that email exists, a reset link has been sent.")


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using a reset token",
)
async def reset_password(request: Request, payload: ResetPasswordRequest) -> MessageResponse | JSONResponse:
    session_factory = request.app.state.session_factory

    async with session_factory() as session:
        result = await session.execute(
            select(ClientModel).where(ClientModel.reset_token == payload.token)
        )
        client = result.scalar_one_or_none()

    if not client:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Invalid or expired reset token."},
        )

    if client.reset_token_expires_at and client.reset_token_expires_at < datetime.now(UTC):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Invalid or expired reset token."},
        )

    new_hash = _hash_password(payload.new_password)

    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                update(ClientModel)
                .where(ClientModel.id == client.id)
                .values(
                    password_hash=new_hash,
                    reset_token=None,
                    reset_token_expires_at=None,
                )
            )

    logger.info("password_reset_completed", email=client.owner_email)

    return MessageResponse(message="Password reset successful.")

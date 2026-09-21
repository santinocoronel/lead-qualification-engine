from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.database import Base


class ClientModel(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    plan_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="FREE")
    subscription_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="INACTIVE"
    )
    lemon_squeezy_customer_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    monthly_requests_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100
    )
    monthly_requests_used: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    reset_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reset_token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    alert_80_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    alert_95_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    custom_llm_provider: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    encrypted_api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_clients_api_key_hash", "api_key_hash"),
        Index("ix_clients_owner_email", "owner_email"),
        Index("ix_clients_subscription_status", "subscription_status"),
        Index("ix_clients_reset_token", "reset_token"),
    )

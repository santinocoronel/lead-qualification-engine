"""create clients table

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_email", sa.String(320), nullable=False, unique=True),
        sa.Column("api_key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("plan_tier", sa.String(20), nullable=False, server_default="FREE"),
        sa.Column("subscription_status", sa.String(20), nullable=False, server_default="INACTIVE"),
        sa.Column("lemon_squeezy_customer_id", sa.String(100), nullable=True),
        sa.Column("monthly_requests_limit", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("monthly_requests_used", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_clients_api_key_hash", "clients", ["api_key_hash"])
    op.create_index("ix_clients_owner_email", "clients", ["owner_email"])
    op.create_index("ix_clients_subscription_status", "clients", ["subscription_status"])


def downgrade() -> None:
    op.drop_index("ix_clients_subscription_status", table_name="clients")
    op.drop_index("ix_clients_owner_email", table_name="clients")
    op.drop_index("ix_clients_api_key_hash", table_name="clients")
    op.drop_table("clients")

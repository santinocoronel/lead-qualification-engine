"""add auth, BYOK and usage alert columns to clients

Revision ID: 003
Revises: 002
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("password_hash", sa.String(128), nullable=True))
    op.add_column("clients", sa.Column("reset_token", sa.String(64), nullable=True))
    op.add_column("clients", sa.Column("reset_token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("alert_80_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("alert_95_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("custom_llm_provider", sa.String(20), nullable=True))
    op.add_column("clients", sa.Column("encrypted_api_key", sa.Text(), nullable=True))

    op.create_index("ix_clients_reset_token", "clients", ["reset_token"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_clients_reset_token", table_name="clients")
    op.drop_column("clients", "encrypted_api_key")
    op.drop_column("clients", "custom_llm_provider")
    op.drop_column("clients", "alert_95_sent_at")
    op.drop_column("clients", "alert_80_sent_at")
    op.drop_column("clients", "reset_token_expires_at")
    op.drop_column("clients", "reset_token")
    op.drop_column("clients", "password_hash")

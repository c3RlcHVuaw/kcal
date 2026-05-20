"""add apple health daily sync state

Revision ID: 0009_apple_health_daily_syncs
Revises: 0008_apple_health
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_apple_health_daily_syncs"
down_revision = "0008_apple_health"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "apple_health_daily_syncs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sync_date", sa.Date(), nullable=False),
        sa.Column("metric", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "sync_date", "metric"),
    )
    op.create_index(
        "ix_apple_health_sync_user_date",
        "apple_health_daily_syncs",
        ["user_id", "sync_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_apple_health_sync_user_date", table_name="apple_health_daily_syncs")
    op.drop_table("apple_health_daily_syncs")

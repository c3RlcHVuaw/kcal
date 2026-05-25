"""add quality events

Revision ID: 0017_quality_events
Revises: 0016_payment_charge_idempotency
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017_quality_events"
down_revision = "0016_payment_charge_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quality_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("query", sa.String(length=512), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quality_events_type_created", "quality_events", ["event_type", "created_at"])
    op.create_index("ix_quality_events_user_created", "quality_events", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_quality_events_user_created", table_name="quality_events")
    op.drop_index("ix_quality_events_type_created", table_name="quality_events")
    op.drop_table("quality_events")

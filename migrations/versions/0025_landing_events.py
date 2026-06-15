"""add landing analytics events

Revision ID: 0025_landing_events
Revises: 0024_subscription_reminders
Create Date: 2026-06-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_landing_events"
down_revision = "0024_subscription_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "landing_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("referrer", sa.String(length=512), nullable=True),
        sa.Column("utm_source", sa.String(length=128), nullable=True),
        sa.Column("utm_medium", sa.String(length=128), nullable=True),
        sa.Column("utm_campaign", sa.String(length=128), nullable=True),
        sa.Column("utm_content", sa.String(length=128), nullable=True),
        sa.Column("utm_term", sa.String(length=128), nullable=True),
        sa.Column("visitor_id", sa.String(length=64), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_landing_events_created", "landing_events", ["created_at"])
    op.create_index("ix_landing_events_type_created", "landing_events", ["event_type", "created_at"])
    op.create_index("ix_landing_events_visitor_created", "landing_events", ["visitor_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_landing_events_visitor_created", table_name="landing_events")
    op.drop_index("ix_landing_events_type_created", table_name="landing_events")
    op.drop_index("ix_landing_events_created", table_name="landing_events")
    op.drop_table("landing_events")

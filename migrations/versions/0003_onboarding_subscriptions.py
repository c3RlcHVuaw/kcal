"""add onboarding and subscriptions

Revision ID: 0003_onboarding_subscriptions
Revises: 0002_ai_usage
Create Date: 2026-05-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_onboarding_subscriptions"
down_revision = "0002_ai_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("language", sa.String(length=8), nullable=False, server_default="ru"),
    )
    op.add_column(
        "users",
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("subscription_expires_at", sa.DateTime(timezone=True)))

    op.create_table(
        "payments",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount_stars", sa.Integer(), nullable=False),
        sa.Column("payload", sa.String(length=128), nullable=False),
        sa.Column("telegram_payment_charge_id", sa.String(length=255), nullable=False),
        sa.Column("provider_payment_charge_id", sa.String(length=255)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_payments_user_created", "payments", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_payments_user_created", table_name="payments")
    op.drop_table("payments")
    op.drop_column("users", "subscription_expires_at")
    op.drop_column("users", "onboarding_completed")
    op.drop_column("users", "language")


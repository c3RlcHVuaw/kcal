"""add subscription plan

Revision ID: 0014_subscription_plans
Revises: 0013_yookassa_payment_statuses
Create Date: 2026-05-21
"""

from __future__ import annotations

from alembic import op

revision = "0014_subscription_plans"
down_revision = "0013_yookassa_payment_statuses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "subscription_plan VARCHAR(32) NOT NULL DEFAULT 'basic'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS subscription_plan")

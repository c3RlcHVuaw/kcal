"""add user birth date

Revision ID: 0015_user_birth_date
Revises: 0014_subscription_plans
Create Date: 2026-05-21
"""

from __future__ import annotations

from alembic import op

revision = "0015_user_birth_date"
down_revision = "0014_subscription_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS birth_date DATE")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS birth_date")

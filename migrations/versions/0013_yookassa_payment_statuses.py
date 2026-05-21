"""add yookassa payment statuses

Revision ID: 0013_yookassa_payment_statuses
Revises: 0012_weekly_mission_bonus
Create Date: 2026-05-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_yookassa_payment_statuses"
down_revision = "0012_weekly_mission_bonus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("payments", "amount_stars", existing_type=sa.Integer(), nullable=True)
    op.alter_column(
        "payments",
        "telegram_payment_charge_id",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS amount_kopecks INTEGER")
    op.execute(
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS "
        "currency VARCHAR(8) NOT NULL DEFAULT 'XTR'"
    )
    op.execute(
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS "
        "method VARCHAR(32) NOT NULL DEFAULT 'stars'"
    )
    op.execute(
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS "
        "status VARCHAR(32) NOT NULL DEFAULT 'succeeded'"
    )
    op.execute(
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS yookassa_payment_id VARCHAR(255)"
    )
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS confirmation_url VARCHAR(1024)")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS paid_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS last_error VARCHAR(512)")
    op.execute(
        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS "
        "updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "uq_payments_yookassa_payment_id ON payments (yookassa_payment_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_payments_status_expires "
        "ON payments (status, expires_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_payments_status_expires")
    op.execute("DROP INDEX IF EXISTS uq_payments_yookassa_payment_id")
    op.drop_column("payments", "updated_at")
    op.drop_column("payments", "last_error")
    op.drop_column("payments", "paid_at")
    op.drop_column("payments", "expires_at")
    op.drop_column("payments", "confirmation_url")
    op.drop_column("payments", "yookassa_payment_id")
    op.drop_column("payments", "status")
    op.drop_column("payments", "method")
    op.drop_column("payments", "currency")
    op.drop_column("payments", "amount_kopecks")
    op.alter_column(
        "payments",
        "telegram_payment_charge_id",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.alter_column("payments", "amount_stars", existing_type=sa.Integer(), nullable=False)

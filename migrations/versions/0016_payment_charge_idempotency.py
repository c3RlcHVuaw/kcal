"""add payment charge idempotency indexes

Revision ID: 0016_payment_charge_idempotency
Revises: 0015_user_birth_date
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op

revision = "0016_payment_charge_idempotency"
down_revision = "0015_user_birth_date"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_payments_telegram_charge
        ON payments (telegram_payment_charge_id)
        WHERE telegram_payment_charge_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_payments_provider_charge
        ON payments (provider_payment_charge_id)
        WHERE provider_payment_charge_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_payments_provider_charge")
    op.execute("DROP INDEX IF EXISTS ux_payments_telegram_charge")

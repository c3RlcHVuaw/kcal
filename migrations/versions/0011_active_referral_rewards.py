"""add active referral reward state

Revision ID: 0011_active_referral_rewards
Revises: 0010_growth_referrals
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op

revision = "0011_active_referral_rewards"
down_revision = "0010_growth_referrals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_at TIMESTAMP WITH TIME ZONE")
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "active_referral_rewarded_at TIMESTAMP WITH TIME ZONE"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "first_active_referral_rewarded_at TIMESTAMP WITH TIME ZONE"
    )
    op.execute(
        "UPDATE users SET referred_at = created_at "
        "WHERE referred_by_user_id IS NOT NULL AND referred_at IS NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS first_active_referral_rewarded_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS active_referral_rewarded_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS referred_at")

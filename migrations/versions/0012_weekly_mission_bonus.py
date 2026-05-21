"""add weekly mission bonus state

Revision ID: 0012_weekly_mission_bonus
Revises: 0011_active_referral_rewards
Create Date: 2026-05-21
"""

from __future__ import annotations

from alembic import op

revision = "0012_weekly_mission_bonus"
down_revision = "0011_active_referral_rewards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS weekly_mission_bonus_week DATE")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS weekly_mission_bonus_week")

"""add referrals and growth offers

Revision ID: 0010_growth_referrals
Revises: 0009_apple_health_daily_syncs
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_growth_referrals"
down_revision = "0009_apple_health_daily_syncs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("referral_code", sa.String(length=32)))
    op.add_column("users", sa.Column("referred_by_user_id", sa.BigInteger()))
    op.add_column("users", sa.Column("referral_rewarded_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("premium_trial_used_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("winback_used_at", sa.DateTime(timezone=True)))
    op.create_unique_constraint("uq_users_referral_code", "users", ["referral_code"])
    op.create_foreign_key(
        "fk_users_referred_by_user_id",
        "users",
        "users",
        ["referred_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_users_referred_by_user_id", "users", ["referred_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_users_referred_by_user_id", table_name="users")
    op.drop_constraint("fk_users_referred_by_user_id", "users", type_="foreignkey")
    op.drop_constraint("uq_users_referral_code", "users", type_="unique")
    op.drop_column("users", "winback_used_at")
    op.drop_column("users", "premium_trial_used_at")
    op.drop_column("users", "referral_rewarded_at")
    op.drop_column("users", "referred_by_user_id")
    op.drop_column("users", "referral_code")

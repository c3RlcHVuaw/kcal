"""add active referral reward state

Revision ID: 0011_active_referral_rewards
Revises: 0010_growth_referrals
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_active_referral_rewards"
down_revision = "0010_growth_referrals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("users")}

    if "referred_at" not in columns:
        op.add_column("users", sa.Column("referred_at", sa.DateTime(timezone=True)))
    if "active_referral_rewarded_at" not in columns:
        op.add_column("users", sa.Column("active_referral_rewarded_at", sa.DateTime(timezone=True)))
    if "first_active_referral_rewarded_at" not in columns:
        op.add_column(
            "users",
            sa.Column("first_active_referral_rewarded_at", sa.DateTime(timezone=True)),
        )
    op.execute(
        "UPDATE users SET referred_at = created_at "
        "WHERE referred_by_user_id IS NOT NULL AND referred_at IS NULL"
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("users")}

    if "first_active_referral_rewarded_at" in columns:
        op.drop_column("users", "first_active_referral_rewarded_at")
    if "active_referral_rewarded_at" in columns:
        op.drop_column("users", "active_referral_rewarded_at")
    if "referred_at" in columns:
        op.drop_column("users", "referred_at")

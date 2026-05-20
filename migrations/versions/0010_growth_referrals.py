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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("users")}

    if "referral_code" not in columns:
        op.add_column("users", sa.Column("referral_code", sa.String(length=32)))
    if "referred_by_user_id" not in columns:
        op.add_column("users", sa.Column("referred_by_user_id", sa.BigInteger()))
    if "referral_rewarded_at" not in columns:
        op.add_column("users", sa.Column("referral_rewarded_at", sa.DateTime(timezone=True)))
    if "premium_trial_used_at" not in columns:
        op.add_column("users", sa.Column("premium_trial_used_at", sa.DateTime(timezone=True)))
    if "winback_used_at" not in columns:
        op.add_column("users", sa.Column("winback_used_at", sa.DateTime(timezone=True)))

    unique_constraints = {
        constraint["name"] for constraint in inspector.get_unique_constraints("users")
    }
    if "uq_users_referral_code" not in unique_constraints:
        op.create_unique_constraint("uq_users_referral_code", "users", ["referral_code"])

    foreign_keys = {foreign_key["name"] for foreign_key in inspector.get_foreign_keys("users")}
    if "fk_users_referred_by_user_id" not in foreign_keys:
        op.create_foreign_key(
            "fk_users_referred_by_user_id",
            "users",
            "users",
            ["referred_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_referred_by_user_id" not in indexes:
        op.create_index("ix_users_referred_by_user_id", "users", ["referred_by_user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("users")}
    foreign_keys = {foreign_key["name"] for foreign_key in inspector.get_foreign_keys("users")}
    unique_constraints = {
        constraint["name"] for constraint in inspector.get_unique_constraints("users")
    }
    columns = {column["name"] for column in inspector.get_columns("users")}

    if "ix_users_referred_by_user_id" in indexes:
        op.drop_index("ix_users_referred_by_user_id", table_name="users")
    if "fk_users_referred_by_user_id" in foreign_keys:
        op.drop_constraint("fk_users_referred_by_user_id", "users", type_="foreignkey")
    if "uq_users_referral_code" in unique_constraints:
        op.drop_constraint("uq_users_referral_code", "users", type_="unique")
    if "winback_used_at" in columns:
        op.drop_column("users", "winback_used_at")
    if "premium_trial_used_at" in columns:
        op.drop_column("users", "premium_trial_used_at")
    if "referral_rewarded_at" in columns:
        op.drop_column("users", "referral_rewarded_at")
    if "referred_by_user_id" in columns:
        op.drop_column("users", "referred_by_user_id")
    if "referral_code" in columns:
        op.drop_column("users", "referral_code")

"""add tracking, favorites, and macro targets

Revision ID: 0004_tracking_and_targets
Revises: 0003_onboarding_subscriptions
Create Date: 2026-05-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_tracking_and_targets"
down_revision = "0003_onboarding_subscriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("protein_target_g", sa.Float()))
    op.add_column("users", sa.Column("fat_target_g", sa.Float()))
    op.add_column("users", sa.Column("carbs_target_g", sa.Float()))
    op.add_column(
        "users",
        sa.Column("reminders_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("dinner_reminder_time", sa.String(length=5), server_default="20:30"),
    )
    op.add_column(
        "users",
        sa.Column("weight_reminder_time", sa.String(length=5), server_default="09:00"),
    )
    op.add_column("users", sa.Column("last_dinner_reminder_date", sa.Date()))
    op.add_column("users", sa.Column("last_weight_reminder_date", sa.Date()))

    op.create_table(
        "favorite_foods",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("food_name", sa.String(length=255), nullable=False),
        sa.Column("kcal", sa.Float(), nullable=False),
        sa.Column("protein", sa.Float(), nullable=False, server_default="0"),
        sa.Column("fat", sa.Float(), nullable=False, server_default="0"),
        sa.Column("carbs", sa.Float(), nullable=False, server_default="0"),
        sa.Column("weight_g", sa.Float()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_favorite_foods_user_created",
        "favorite_foods",
        ["user_id", "created_at"],
    )

    op.create_table(
        "water_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount_ml", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_water_logs_user_created", "water_logs", ["user_id", "created_at"])

    op.create_table(
        "weight_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_weight_logs_user_created", "weight_logs", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_weight_logs_user_created", table_name="weight_logs")
    op.drop_table("weight_logs")
    op.drop_index("ix_water_logs_user_created", table_name="water_logs")
    op.drop_table("water_logs")
    op.drop_index("ix_favorite_foods_user_created", table_name="favorite_foods")
    op.drop_table("favorite_foods")
    op.drop_column("users", "last_weight_reminder_date")
    op.drop_column("users", "last_dinner_reminder_date")
    op.drop_column("users", "weight_reminder_time")
    op.drop_column("users", "dinner_reminder_time")
    op.drop_column("users", "reminders_enabled")
    op.drop_column("users", "carbs_target_g")
    op.drop_column("users", "fat_target_g")
    op.drop_column("users", "protein_target_g")

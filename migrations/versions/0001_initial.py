"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Europe/Samara"),
        sa.Column("gender", sa.String(length=32), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("height", sa.Float(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("activity", sa.String(length=64), nullable=True),
        sa.Column("goal", sa.String(length=64), nullable=True),
        sa.Column("daily_kcal_target", sa.Integer(), nullable=False, server_default="2200"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    op.create_table(
        "food_entries",
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
        sa.Column("weight_g", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_food_entries_user_created", "food_entries", ["user_id", "created_at"])

    op.create_table(
        "products_cache",
        sa.Column("barcode", sa.String(length=64), primary_key=True),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("kcal_100g", sa.Float(), nullable=True),
        sa.Column("protein_100g", sa.Float(), nullable=True),
        sa.Column("fat_100g", sa.Float(), nullable=True),
        sa.Column("carbs_100g", sa.Float(), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("products_cache")
    op.drop_index("ix_food_entries_user_created", table_name="food_entries")
    op.drop_table("food_entries")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")

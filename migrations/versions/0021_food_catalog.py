"""add searchable food catalog

Revision ID: 0021_food_catalog
Revises: 0020_food_entry_meal_type
Create Date: 2026-06-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021_food_catalog"
down_revision = "0020_food_entry_meal_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "food_catalog_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("food_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("kcal", sa.Float(), nullable=False),
        sa.Column("protein", sa.Float(), nullable=False, server_default="0"),
        sa.Column("fat", sa.Float(), nullable=False, server_default="0"),
        sa.Column("carbs", sa.Float(), nullable=False, server_default="0"),
        sa.Column("weight_g", sa.Float(), nullable=True),
        sa.Column("emoji", sa.String(length=16), nullable=True),
        sa.Column("advice", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("trust_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confirmed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_food_catalog_items_user_id", "food_catalog_items", ["user_id"])
    op.create_index(
        "ix_food_catalog_items_normalized",
        "food_catalog_items",
        ["normalized_name"],
    )
    op.create_index(
        "ix_food_catalog_items_source_trust",
        "food_catalog_items",
        ["source", "trust_score"],
    )

    op.create_table(
        "food_catalog_aliases",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "item_id",
            sa.BigInteger(),
            sa.ForeignKey("food_catalog_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("normalized_alias", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="system"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("item_id", "normalized_alias"),
    )
    op.create_index(
        "ix_food_catalog_aliases_normalized",
        "food_catalog_aliases",
        ["normalized_alias"],
    )


def downgrade() -> None:
    op.drop_index("ix_food_catalog_aliases_normalized", table_name="food_catalog_aliases")
    op.drop_table("food_catalog_aliases")
    op.drop_index("ix_food_catalog_items_source_trust", table_name="food_catalog_items")
    op.drop_index("ix_food_catalog_items_normalized", table_name="food_catalog_items")
    op.drop_index("ix_food_catalog_items_user_id", table_name="food_catalog_items")
    op.drop_table("food_catalog_items")

"""add meal type to food entries

Revision ID: 0020_food_entry_meal_type
Revises: 0019_promo_codes
Create Date: 2026-05-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020_food_entry_meal_type"
down_revision = "0019_promo_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("food_entries", sa.Column("meal_type", sa.String(length=32), nullable=True))
    op.create_index("ix_food_entries_user_meal", "food_entries", ["user_id", "meal_type"])


def downgrade() -> None:
    op.drop_index("ix_food_entries_user_meal", table_name="food_entries")
    op.drop_column("food_entries", "meal_type")

"""add food entry photo thumbnails

Revision ID: 0023_food_entry_photo_thumbs
Revises: 0022_admin_settings
Create Date: 2026-06-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023_food_entry_photo_thumbs"
down_revision = "0022_admin_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("food_entries", sa.Column("photo_thumb_data_url", sa.Text(), nullable=True))
    op.add_column(
        "food_entries",
        sa.Column("photo_thumb_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("food_entries", "photo_thumb_expires_at")
    op.drop_column("food_entries", "photo_thumb_data_url")

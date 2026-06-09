"""add subscription reminder marker

Revision ID: 0024_subscription_reminders
Revises: 0023_food_entry_photo_thumbs
Create Date: 2026-06-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024_subscription_reminders"
down_revision = "0023_food_entry_photo_thumbs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_subscription_reminder_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_subscription_reminder_date")

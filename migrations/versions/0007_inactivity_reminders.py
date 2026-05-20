"""add inactivity reminder tracking

Revision ID: 0007_inactivity_reminders
Revises: 0006_food_insights
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_inactivity_reminders"
down_revision = "0006_food_insights"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_inactivity_reminder_date", sa.Date()))


def downgrade() -> None:
    op.drop_column("users", "last_inactivity_reminder_date")

"""add food insights and smart reminder settings

Revision ID: 0006_food_insights
Revises: 0005_activity_logs
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_food_insights"
down_revision = "0005_activity_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("food_entries", sa.Column("emoji", sa.String(length=16)))
    op.add_column("food_entries", sa.Column("advice", sa.String(length=255)))
    op.add_column("favorite_foods", sa.Column("emoji", sa.String(length=16)))
    op.add_column("favorite_foods", sa.Column("advice", sa.String(length=255)))

    op.add_column(
        "users",
        sa.Column(
            "meal_reminders_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "weight_reminders_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("breakfast_reminder_time", sa.String(length=5), server_default="10:00"),
    )
    op.add_column(
        "users",
        sa.Column("lunch_reminder_time", sa.String(length=5), server_default="14:00"),
    )
    op.add_column("users", sa.Column("last_breakfast_reminder_date", sa.Date()))
    op.add_column("users", sa.Column("last_lunch_reminder_date", sa.Date()))


def downgrade() -> None:
    op.drop_column("users", "last_lunch_reminder_date")
    op.drop_column("users", "last_breakfast_reminder_date")
    op.drop_column("users", "lunch_reminder_time")
    op.drop_column("users", "breakfast_reminder_time")
    op.drop_column("users", "weight_reminders_enabled")
    op.drop_column("users", "meal_reminders_enabled")
    op.drop_column("favorite_foods", "advice")
    op.drop_column("favorite_foods", "emoji")
    op.drop_column("food_entries", "advice")
    op.drop_column("food_entries", "emoji")

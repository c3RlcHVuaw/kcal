"""add apple health shortcut token

Revision ID: 0008_apple_health
Revises: 0007_inactivity_reminders
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_apple_health"
down_revision = "0007_inactivity_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("apple_health_token", sa.String(length=64)))
    op.create_index(
        "ix_users_apple_health_token",
        "users",
        ["apple_health_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_users_apple_health_token", table_name="users")
    op.drop_column("users", "apple_health_token")

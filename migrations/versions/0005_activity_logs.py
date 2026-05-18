"""add activity logs

Revision ID: 0005_activity_logs
Revises: 0004_tracking_and_targets
Create Date: 2026-05-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_activity_logs"
down_revision = "0004_tracking_and_targets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("activity_name", sa.String(length=255), nullable=False),
        sa.Column("kcal", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_activity_logs_user_created", "activity_logs", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_activity_logs_user_created", table_name="activity_logs")
    op.drop_table("activity_logs")

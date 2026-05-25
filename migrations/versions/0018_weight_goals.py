"""add weight goals

Revision ID: 0018_weight_goals
Revises: 0017_quality_events
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018_weight_goals"
down_revision = "0017_quality_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("target_weight_kg", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("weekly_weight_change_kg", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "weekly_weight_change_kg")
    op.drop_column("users", "target_weight_kg")

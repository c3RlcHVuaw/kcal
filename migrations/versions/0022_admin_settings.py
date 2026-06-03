"""add admin settings

Revision ID: 0022_admin_settings
Revises: 0021_food_catalog
Create Date: 2026-06-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022_admin_settings"
down_revision = "0021_food_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    admin_settings = sa.table(
        "admin_settings",
        sa.column("key", sa.String),
        sa.column("value", postgresql.JSONB),
    )
    op.bulk_insert(
        admin_settings,
        [
            {
                "key": "openai_balance",
                "value": {
                    "balance_usd": 9.33,
                    "initial_balance_usd": 9.33,
                    "manual_adjustments_usd": 0.0,
                },
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("admin_settings")

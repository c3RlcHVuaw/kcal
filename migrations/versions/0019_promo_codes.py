"""add promo codes

Revision ID: 0019_promo_codes
Revises: 0018_weight_goals
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_promo_codes"
down_revision = "0018_weight_goals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "promo_codes",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("used_count", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_promo_codes_active", "promo_codes", ["active"])
    op.add_column("payments", sa.Column("promo_code_id", sa.BigInteger(), nullable=True))
    op.add_column("payments", sa.Column("original_amount_stars", sa.Integer(), nullable=True))
    op.add_column("payments", sa.Column("original_amount_kopecks", sa.Integer(), nullable=True))
    op.add_column("payments", sa.Column("promo_code", sa.String(length=64), nullable=True))
    op.add_column("payments", sa.Column("promo_discount_percent", sa.Integer(), nullable=True))
    op.create_index("ix_payments_promo_code_id", "payments", ["promo_code_id"])
    op.create_foreign_key(
        "fk_payments_promo_code_id_promo_codes",
        "payments",
        "promo_codes",
        ["promo_code_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_payments_promo_code_id_promo_codes", "payments", type_="foreignkey")
    op.drop_index("ix_payments_promo_code_id", table_name="payments")
    op.drop_column("payments", "promo_discount_percent")
    op.drop_column("payments", "promo_code")
    op.drop_column("payments", "original_amount_kopecks")
    op.drop_column("payments", "original_amount_stars")
    op.drop_column("payments", "promo_code_id")
    op.drop_index("ix_promo_codes_active", table_name="promo_codes")
    op.drop_table("promo_codes")

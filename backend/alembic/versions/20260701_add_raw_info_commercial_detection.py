"""add raw info commercial detection fields

Revision ID: 20260701_raw_info_commercial
Revises: 20260630_payment_orders
Create Date: 2026-07-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260701_raw_info_commercial"
down_revision: Union[str, None] = "20260630_payment_orders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "raw_infos",
        sa.Column("commercial_level", sa.String(length=20), nullable=False, server_default="none"),
    )
    op.add_column(
        "raw_infos",
        sa.Column("commercial_meta", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True),
    )
    op.create_index(op.f("ix_raw_infos_commercial_level"), "raw_infos", ["commercial_level"], unique=False)
    op.alter_column("raw_infos", "commercial_level", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_raw_infos_commercial_level"), table_name="raw_infos")
    op.drop_column("raw_infos", "commercial_meta")
    op.drop_column("raw_infos", "commercial_level")

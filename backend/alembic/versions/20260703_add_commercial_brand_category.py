"""add commercial brand and category fields to raw_infos

Revision ID: 20260703_commercial_brand_cat
Revises: 20260703_raw_info_html
Create Date: 2026-07-03 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260703_commercial_brand_cat"
down_revision: Union[str, None] = "20260703_raw_info_html"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "raw_infos",
        sa.Column("commercial_brand", sa.String(100), nullable=True),
    )
    op.add_column(
        "raw_infos",
        sa.Column("commercial_category", sa.String(50), nullable=True),
    )
    op.create_index(
        "ix_raw_infos_commercial_brand",
        "raw_infos",
        ["commercial_brand"],
    )
    op.create_index(
        "ix_raw_infos_commercial_category",
        "raw_infos",
        ["commercial_category"],
    )


def downgrade() -> None:
    op.drop_index("ix_raw_infos_commercial_category", table_name="raw_infos")
    op.drop_index("ix_raw_infos_commercial_brand", table_name="raw_infos")
    op.drop_column("raw_infos", "commercial_category")
    op.drop_column("raw_infos", "commercial_brand")

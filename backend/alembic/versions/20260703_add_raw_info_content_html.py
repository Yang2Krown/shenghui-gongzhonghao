"""add content_html column to raw_infos

Revision ID: 20260703_raw_info_html
Revises: 20260701_raw_info_commercial
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260703_raw_info_html"
down_revision: Union[str, None] = "20260701_user_profile_persona"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "raw_infos",
        sa.Column("content_html", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("raw_infos", "content_html")

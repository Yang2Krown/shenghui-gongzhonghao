"""add persona to user profiles

Revision ID: 20260701_user_profile_persona
Revises: 20260701_raw_info_commercial
Create Date: 2026-07-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260701_user_profile_persona"
down_revision: Union[str, None] = "20260701_raw_info_commercial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("persona", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_profiles", "persona")

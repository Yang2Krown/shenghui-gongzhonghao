"""add latest_title on info_clusters

Revision ID: 20260529_latest_title
Revises: 20260527_gen_records
Create Date: 2026-05-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260529_latest_title'
down_revision: Union[str, None] = '20260527_gen_records'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'info_clusters',
        sa.Column('latest_title', sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('info_clusters', 'latest_title')

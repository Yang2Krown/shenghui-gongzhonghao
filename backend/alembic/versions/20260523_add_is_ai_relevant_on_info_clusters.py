"""add is_ai_relevant on info_clusters

Revision ID: 20260523_add_is_ai_relevant
Revises: 22ab956b7d3b
Create Date: 2026-05-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260523_add_is_ai_relevant'
down_revision: Union[str, None] = '22ab956b7d3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'info_clusters',
        sa.Column('is_ai_relevant', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        'ix_info_clusters_is_ai_relevant',
        'info_clusters',
        ['is_ai_relevant'],
    )


def downgrade() -> None:
    op.drop_index('ix_info_clusters_is_ai_relevant', table_name='info_clusters')
    op.drop_column('info_clusters', 'is_ai_relevant')

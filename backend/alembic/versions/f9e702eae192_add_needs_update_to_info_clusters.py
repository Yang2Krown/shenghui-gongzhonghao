"""add_needs_update_to_info_clusters

Revision ID: f9e702eae192
Revises: da97a9e7a456
Create Date: 2026-06-11 16:57:55.894804

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f9e702eae192'
down_revision: Union[str, None] = 'da97a9e7a456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('info_clusters', sa.Column('needs_update', sa.Boolean(), nullable=True))
    op.create_index(op.f('ix_info_clusters_needs_update'), 'info_clusters', ['needs_update'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_info_clusters_needs_update'), table_name='info_clusters')
    op.drop_column('info_clusters', 'needs_update')

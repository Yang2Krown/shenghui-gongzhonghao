"""make info_cluster_id nullable on topic_candidates

Revision ID: 20260527_nullable_cluster
Revises: f7a1b2c3d4e5
Create Date: 2026-05-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260527_nullable_cluster'
down_revision: Union[str, None] = 'f7a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'topic_candidates',
        'info_cluster_id',
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'topic_candidates',
        'info_cluster_id',
        existing_type=sa.Integer(),
        nullable=False,
    )

"""add xhs_topic_boards snapshot table

Revision ID: 20260724_xhs_topic_boards
Revises: 20260718_xhs_topics
Create Date: 2026-07-24 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260724_xhs_topic_boards'
down_revision: Union[str, None] = '20260718_xhs_topics'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'xhs_topic_boards',
        sa.Column('edition_date', sa.Date(), nullable=False),
        sa.Column('wave', sa.String(length=20), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_xhs_topic_boards_edition_date'), 'xhs_topic_boards', ['edition_date'], unique=False)
    op.create_index(op.f('ix_xhs_topic_boards_id'), 'xhs_topic_boards', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_xhs_topic_boards_id'), table_name='xhs_topic_boards')
    op.drop_index(op.f('ix_xhs_topic_boards_edition_date'), table_name='xhs_topic_boards')
    op.drop_table('xhs_topic_boards')

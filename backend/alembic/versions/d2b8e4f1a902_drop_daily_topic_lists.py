"""drop_daily_topic_lists

每日清单功能下线（全局排序、无人使用）。删表。

Revision ID: d2b8e4f1a902
Revises: c1a7f3e8b201
Create Date: 2026-06-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd2b8e4f1a902'
down_revision: Union[str, None] = 'c1a7f3e8b201'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 先删子表（FK 指向 daily_topic_lists / topic_candidates）
    op.execute("DROP TABLE IF EXISTS daily_topic_list_items CASCADE")
    op.execute("DROP TABLE IF EXISTS daily_topic_lists CASCADE")


def downgrade() -> None:
    op.create_table(
        'daily_topic_lists',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('list_date', sa.Date(), nullable=False),
        sa.Column('top_n', sa.Integer(), nullable=True),
        sa.Column('items', sa.JSON(), nullable=True),
        sa.Column('direction_distribution', sa.JSON(), nullable=True),
        sa.Column('notes', sa.JSON(), nullable=True),
    )
    op.create_index('ix_daily_topic_lists_list_date', 'daily_topic_lists', ['list_date'], unique=True)
    op.create_table(
        'daily_topic_list_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('list_id', sa.Integer(), sa.ForeignKey('daily_topic_lists.id'), nullable=False),
        sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('topic_candidates.id'), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('score_snapshot', sa.Float(), nullable=True),
    )
    op.create_index('ix_daily_topic_list_items_list_id', 'daily_topic_list_items', ['list_id'])
    op.create_index('ix_daily_topic_list_items_candidate_id', 'daily_topic_list_items', ['candidate_id'])

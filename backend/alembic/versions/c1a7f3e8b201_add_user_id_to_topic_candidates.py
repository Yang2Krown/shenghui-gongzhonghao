"""add_user_id_to_topic_candidates

挖掘结果按用户隔离：候选选题归触发挖掘/创建的用户所有。
历史候选 user_id 保持 NULL（对所有人不可见，由 14 天清理逐步消化）。

Revision ID: c1a7f3e8b201
Revises: d8b2e5a1c7f4
Create Date: 2026-06-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c1a7f3e8b201'
down_revision: Union[str, None] = 'd8b2e5a1c7f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('topic_candidates', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_topic_candidates_user_id'), 'topic_candidates', ['user_id'], unique=False)
    op.create_foreign_key(
        'fk_topic_candidates_user_id_users',
        'topic_candidates', 'users',
        ['user_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_topic_candidates_user_id_users', 'topic_candidates', type_='foreignkey')
    op.drop_index(op.f('ix_topic_candidates_user_id'), table_name='topic_candidates')
    op.drop_column('topic_candidates', 'user_id')

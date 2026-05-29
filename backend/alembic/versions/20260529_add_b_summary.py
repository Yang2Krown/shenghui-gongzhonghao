"""add b_summary column to title_candidates

Revision ID: 20260529_b_summary
Revises: 20260527_gen_records
Create Date: 2026-05-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260529_b_summary'
down_revision: Union[str, None] = '20260527_gen_records'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'title_candidates',
        sa.Column('b_summary', sa.Text(), nullable=True, comment='Agent B 生成的标题简介'),
    )


def downgrade() -> None:
    op.drop_column('title_candidates', 'b_summary')

"""add_enriched_summary_to_topic_candidates

Revision ID: da97a9e7a456
Revises: 6fb0ceb2fe62
Create Date: 2026-06-05 17:12:21.986574

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'da97a9e7a456'
down_revision: Union[str, None] = '6fb0ceb2fe62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agent A2 充实后的选题简介
    op.add_column('topic_candidates', sa.Column('enriched_summary', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('topic_candidates', 'enriched_summary')

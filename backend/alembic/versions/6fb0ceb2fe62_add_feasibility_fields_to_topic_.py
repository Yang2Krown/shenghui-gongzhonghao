"""add_feasibility_fields_to_topic_candidates

Revision ID: 6fb0ceb2fe62
Revises: 20260530_summary
Create Date: 2026-06-05 16:56:30.522160

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6fb0ceb2fe62'
down_revision: Union[str, None] = '20260530_summary'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agent A2 可写性审计字段
    op.add_column('topic_candidates', sa.Column('feasibility_score', sa.Float(), nullable=True))
    op.add_column('topic_candidates', sa.Column('feasibility_passed', sa.Boolean(), nullable=True))
    op.add_column('topic_candidates', sa.Column('feasibility_verdict', sa.String(length=20), nullable=True))
    op.add_column('topic_candidates', sa.Column('feasibility_evidence', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True))
    op.add_column('topic_candidates', sa.Column('feasibility_reasoning', sa.Text(), nullable=True))
    op.add_column('topic_candidates', sa.Column('feasibility_rewrite_suggestion', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('topic_candidates', 'feasibility_rewrite_suggestion')
    op.drop_column('topic_candidates', 'feasibility_reasoning')
    op.drop_column('topic_candidates', 'feasibility_evidence')
    op.drop_column('topic_candidates', 'feasibility_verdict')
    op.drop_column('topic_candidates', 'feasibility_passed')
    op.drop_column('topic_candidates', 'feasibility_score')

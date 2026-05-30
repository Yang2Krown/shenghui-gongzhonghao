"""Add summary column to topic_candidates table

Revision ID: 20260530_summary
Revises: 20260529_latest_title
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '20260530_summary'
down_revision = '20260529_latest_title'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('topic_candidates', sa.Column('summary', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('topic_candidates', 'summary')

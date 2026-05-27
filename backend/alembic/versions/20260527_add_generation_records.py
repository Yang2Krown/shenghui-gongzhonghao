"""add generation_records table

Revision ID: 20260527_gen_records
Revises: 20260527_nullable_cluster
Create Date: 2026-05-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '20260527_gen_records'
down_revision: Union[str, None] = '20260527_nullable_cluster'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'generation_records',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('type', sa.String(40), nullable=False),
        sa.Column('run_id', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('input_snapshot', postgresql.JSONB(), server_default='{}'),
        sa.Column('output_snapshot', postgresql.JSONB(), nullable=True),
        sa.Column('display_title', sa.String(500), nullable=True),
        sa.Column('parent_record_id', sa.Integer(), sa.ForeignKey('generation_records.id'), nullable=True),
        sa.Column('creation_id', sa.Integer(), sa.ForeignKey('content_creations.id'), nullable=True),
        sa.Column('candidate_id', sa.Integer(), nullable=True),
        sa.Column('resume_context', postgresql.JSONB(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_generation_records_user_id', 'generation_records', ['user_id'])
    op.create_index('ix_generation_records_type', 'generation_records', ['type'])
    op.create_index('ix_generation_records_run_id', 'generation_records', ['run_id'], unique=True)
    op.create_index('ix_generation_records_creation_id', 'generation_records', ['creation_id'])
    op.create_index('ix_generation_records_candidate_id', 'generation_records', ['candidate_id'])


def downgrade() -> None:
    op.drop_table('generation_records')

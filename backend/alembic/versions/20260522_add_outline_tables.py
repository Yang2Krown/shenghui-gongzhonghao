"""添加大纲生成相关表。

Revision ID: 20260522_add_outline_tables
Revises: fff298cde66a
Create Date: 2026-05-22 10:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260522_add_outline_tables'
down_revision = 'fff298cde66a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 outlines 表
    op.create_table(
        'outlines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('topic_candidates.id'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('direction', sa.String(50), nullable=True),
        sa.Column('routine', sa.String(200), nullable=True),
        sa.Column('sections', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('total_words', sa.Integer(), nullable=True),
        sa.Column('section_count', sa.Integer(), nullable=True),
        sa.Column('generation_process', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('inspection_score', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('total_score', sa.Float(), nullable=True),
        sa.Column('passed', sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_outline_candidate', 'outlines', ['candidate_id'])
    op.create_index('ix_outline_passed', 'outlines', ['passed'])
    
    # 创建 outline_candidates 表
    op.create_table(
        'outline_candidates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('outline_id', sa.Integer(), sa.ForeignKey('outlines.id'), nullable=False),
        sa.Column('candidate_number', sa.Integer(), nullable=False),
        sa.Column('hook_type', sa.String(50), nullable=False),
        sa.Column('skeleton_feature', sa.Text(), nullable=True),
        sa.Column('sections', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('total_words', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_outline_candidate_outline', 'outline_candidates', ['outline_id'])
    
    # 创建 outline_reviews 表
    op.create_table(
        'outline_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('outline_id', sa.Integer(), sa.ForeignKey('outlines.id'), nullable=False),
        sa.Column('selected_candidate', sa.Integer(), nullable=True),
        sa.Column('review_reason', sa.Text(), nullable=True),
        sa.Column('reviewed_sections', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_outline_review_outline', 'outline_reviews', ['outline_id'], unique=True)
    
    # 创建 outline_criticisms 表
    op.create_table(
        'outline_criticisms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('outline_id', sa.Integer(), sa.ForeignKey('outlines.id'), nullable=False),
        sa.Column('overall_feeling', sa.Text(), nullable=True),
        sa.Column('problem_sections', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('revised_sections', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_outline_criticism_outline', 'outline_criticisms', ['outline_id'], unique=True)
    
    # 创建 outline_inspections 表
    op.create_table(
        'outline_inspections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('outline_id', sa.Integer(), sa.ForeignKey('outlines.id'), nullable=False),
        sa.Column('hook_score', sa.Float(), nullable=True),
        sa.Column('value_ladder_score', sa.Float(), nullable=True),
        sa.Column('rhythm_score', sa.Float(), nullable=True),
        sa.Column('title_scan_score', sa.Float(), nullable=True),
        sa.Column('trigger_score', sa.Float(), nullable=True),
        sa.Column('length_score', sa.Float(), nullable=True),
        sa.Column('total_score', sa.Float(), nullable=True),
        sa.Column('verdict', sa.String(20), nullable=True),
        sa.Column('deduction_reasons', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_outline_inspection_outline', 'outline_inspections', ['outline_id'], unique=True)


def downgrade() -> None:
    op.drop_table('outline_inspections')
    op.drop_table('outline_criticisms')
    op.drop_table('outline_reviews')
    op.drop_table('outline_candidates')
    op.drop_table('outlines')

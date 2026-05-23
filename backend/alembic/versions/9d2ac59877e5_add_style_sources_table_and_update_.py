"""add_style_sources_table_and_update_style_profile

Revision ID: 9d2ac59877e5
Revises: 22ab956b7d3b
Create Date: 2026-05-23 09:53:57.854436

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9d2ac59877e5'
down_revision: Union[str, None] = '22ab956b7d3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """检查列是否存在"""
    bind = op.get_bind()
    result = bind.execute(sa.text(
        f"SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = '{table_name}' AND column_name = '{column_name}')"
    ))
    return result.scalar()


def upgrade() -> None:
    # 添加 style_profiles 新字段（检查是否已存在）
    columns_to_add = [
        ('version', sa.Integer()),
        ('signature', sa.Text()),
        ('radar', sa.JSON()),
        ('traits', sa.JSON()),
        ('source_count', sa.Integer()),
        ('total_words', sa.Integer()),
        ('trained_at', sa.DateTime()),
    ]

    for col_name, col_type in columns_to_add:
        if not column_exists('style_profiles', col_name):
            op.add_column('style_profiles', sa.Column(col_name, col_type, nullable=True))

    # 检查 style_sources 表是否已存在
    bind = op.get_bind()
    table_exists = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'style_sources')"
    )).scalar()

    if not table_exists:
        op.create_table(
            'style_sources',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('profile_id', sa.Integer(), sa.ForeignKey('style_profiles.id'), nullable=True),
            sa.Column('title', sa.String(500), nullable=True),
            sa.Column('content_type', sa.String(50), server_default='text'),
            sa.Column('url', sa.String(1000), nullable=True),
            sa.Column('raw_text', sa.Text(), nullable=True),
            sa.Column('preview', sa.Text(), nullable=True),
            sa.Column('word_count', sa.Integer(), server_default='0'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    table_exists = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'style_sources')"
    )).scalar()

    if table_exists:
        op.drop_table('style_sources')

    columns_to_drop = ['trained_at', 'total_words', 'source_count', 'traits', 'radar', 'signature', 'version']
    for col_name in columns_to_drop:
        if column_exists('style_profiles', col_name):
            op.drop_column('style_profiles', col_name)

"""add course_chapters table

Revision ID: 20260708_course
Revises: 20260707_membership
Create Date: 2026-07-08

"""
from typing import Union, Sequence

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = "20260708_course"
down_revision: Union[str, None] = "20260707_membership"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    table_exists = (
        False
        if context.is_offline_mode()
        else Inspector(op.get_bind()).has_table("course_chapters")
    )
    if not table_exists:
        op.create_table(
            "course_chapters",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("title", sa.String(500), nullable=False, comment="章节标题"),
            sa.Column("subtitle", sa.String(200), nullable=True, comment="副标题"),
            sa.Column("kicker", sa.String(50), nullable=True, comment="章节标签"),
            sa.Column("content_html", sa.Text(), nullable=True, comment="正文 HTML"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0", comment="排序序号"),
            sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("true"), comment="是否发布"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            comment="课程章节",
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_course_chapters_order ON course_chapters (sort_order)")


def downgrade() -> None:
    op.drop_index("ix_course_chapters_order", table_name="course_chapters")
    op.drop_table("course_chapters")

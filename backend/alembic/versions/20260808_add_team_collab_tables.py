"""add team collaboration tables (P0)

员工档案 / 文章共享 —— 纯增量，不影响现有业务表。
角色赋予由管理员在系统内直接操作（无邀请码流程）。

Revision ID: 20260808_team_collab
Revises: 20260807_dajiala
Create Date: 2026-08-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260808_team_collab"
down_revision: Union[str, None] = "20260807_dajiala"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 员工档案：users 一对一
    op.create_table(
        "employee_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("department", sa.String(50), nullable=True, comment="部门"),
        sa.Column("position", sa.String(50), nullable=True, comment="岗位"),
        sa.Column("manager_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, comment="直属上级"),
        sa.Column("employee_no", sa.String(32), nullable=True, comment="工号"),
        sa.Column("joined_at", sa.Date(), nullable=True, comment="入职日期"),
        sa.Column("status", sa.String(20), server_default="active", nullable=False, comment="active/left"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_employee_profiles_user_id", "employee_profiles", ["user_id"])

    # 文章共享：创作 -> 团队成员
    op.create_table(
        "article_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("creation_id", sa.Integer(), sa.ForeignKey("content_creations.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(20), server_default="viewer", nullable=False, comment="owner/editor/viewer"),
        sa.Column("granted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, comment="授权人"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("creation_id", "user_id", name="uq_article_members_creation_user"),
    )
    op.create_index("ix_article_members_creation_id", "article_members", ["creation_id"])
    op.create_index("ix_article_members_user_id", "article_members", ["user_id"])

def downgrade() -> None:
    op.drop_index("ix_article_members_user_id", table_name="article_members")
    op.drop_index("ix_article_members_creation_id", table_name="article_members")
    op.drop_table("article_members")
    op.drop_index("ix_employee_profiles_user_id", table_name="employee_profiles")
    op.drop_table("employee_profiles")

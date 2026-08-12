"""add article versions and experience cards.

Revision ID: 20260811_phase1c
Revises: 20260811_meeting_dedup
Create Date: 2026-08-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260811_phase1c"
down_revision: Union[str, None] = "20260811_meeting_dedup"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("creation_id", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("suggestion_id", sa.Integer(), nullable=True),
        sa.Column("diff_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["creation_id"],
            ["content_creations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["suggestion_id"],
            ["meeting_suggestions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "creation_id",
            "version_no",
            name="uq_content_versions_creation_version_no",
        ),
    )
    op.create_index("ix_content_versions_creation_id", "content_versions", ["creation_id"])
    op.create_index("ix_content_versions_version_type", "content_versions", ["version_type"])
    op.create_index("ix_content_versions_created_by", "content_versions", ["created_by"])
    op.create_index("ix_content_versions_suggestion_id", "content_versions", ["suggestion_id"])
    op.create_index(
        "ix_content_versions_creation_version_no",
        "content_versions",
        ["creation_id", "version_no"],
    )
    op.create_index(
        "ix_content_versions_creation_created_at",
        "content_versions",
        ["creation_id", "created_at"],
    )

    # Phase 1b 先保留了整数引用；先清理历史上可能存在的孤儿值，
    # 再补上真正的 SET NULL 外键，避免迁移被旧数据卡住。
    op.execute(
        sa.text(
            """
            UPDATE meeting_suggestions
            SET related_version_id = NULL
            WHERE related_version_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM content_versions
                  WHERE content_versions.id = meeting_suggestions.related_version_id
              )
            """
        )
    )
    op.create_foreign_key(
        "fk_meeting_suggestions_related_version_id_content_versions",
        "meeting_suggestions",
        "content_versions",
        ["related_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "experience_cards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("creation_id", sa.Integer(), nullable=True),
        sa.Column("version_pair", sa.JSON(), nullable=True),
        sa.Column("suggestion_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("embedding_status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("embedding_error", sa.Text(), nullable=True),
        sa.Column("embedding_task_id", sa.String(length=100), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["creation_id"],
            ["content_creations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["suggestion_id"],
            ["meeting_suggestions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_experience_cards_source_type", "experience_cards", ["source_type"])
    op.create_index("ix_experience_cards_creation_id", "experience_cards", ["creation_id"])
    op.create_index("ix_experience_cards_suggestion_id", "experience_cards", ["suggestion_id"])
    op.create_index("ix_experience_cards_category", "experience_cards", ["category"])
    op.create_index("ix_experience_cards_created_by", "experience_cards", ["created_by"])
    op.create_index(
        "ix_experience_cards_source_type_created_at",
        "experience_cards",
        ["source_type", "created_at"],
    )
    op.create_index(
        "ix_experience_cards_category_created_at",
        "experience_cards",
        ["category", "created_at"],
    )
    op.create_index(
        "ix_experience_cards_creation",
        "experience_cards",
        ["creation_id"],
    )
    op.create_index(
        "ix_experience_cards_suggestion",
        "experience_cards",
        ["suggestion_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_experience_cards_suggestion", table_name="experience_cards")
    op.drop_index("ix_experience_cards_creation", table_name="experience_cards")
    op.drop_index("ix_experience_cards_category_created_at", table_name="experience_cards")
    op.drop_index("ix_experience_cards_source_type_created_at", table_name="experience_cards")
    op.drop_index("ix_experience_cards_created_by", table_name="experience_cards")
    op.drop_index("ix_experience_cards_category", table_name="experience_cards")
    op.drop_index("ix_experience_cards_suggestion_id", table_name="experience_cards")
    op.drop_index("ix_experience_cards_creation_id", table_name="experience_cards")
    op.drop_index("ix_experience_cards_source_type", table_name="experience_cards")
    op.drop_table("experience_cards")

    op.drop_constraint(
        "fk_meeting_suggestions_related_version_id_content_versions",
        "meeting_suggestions",
        type_="foreignkey",
    )
    op.drop_index("ix_content_versions_creation_created_at", table_name="content_versions")
    op.drop_index("ix_content_versions_creation_version_no", table_name="content_versions")
    op.drop_index("ix_content_versions_suggestion_id", table_name="content_versions")
    op.drop_index("ix_content_versions_created_by", table_name="content_versions")
    op.drop_index("ix_content_versions_version_type", table_name="content_versions")
    op.drop_index("ix_content_versions_creation_id", table_name="content_versions")
    op.drop_table("content_versions")

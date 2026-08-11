"""phase 1b meeting notes and actionable suggestions.

Revision ID: 20260811_phase1b
Revises: 20260808_phase05
Create Date: 2026-08-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260811_phase1b"
down_revision: Union[str, None] = "20260808_phase05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meetings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("meeting_at", sa.DateTime(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column(
            "source_kind",
            sa.String(length=20),
            server_default="pasted_text",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="extracting",
            nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("extract_task_id", sa.String(length=100), nullable=True),
        sa.Column("extract_run_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meetings_meeting_at", "meetings", ["meeting_at"])
    op.create_index("ix_meetings_status", "meetings", ["status"])
    op.create_index("ix_meetings_created_by", "meetings", ["created_by"])
    op.create_index(
        "ix_meetings_status_meeting_at",
        "meetings",
        ["status", "meeting_at"],
    )
    op.create_index(
        "ix_meetings_created_by_meeting_at",
        "meetings",
        ["created_by", "meeting_at"],
    )

    op.create_table(
        "meeting_suggestions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("proposer", sa.String(length=50), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("acceptance_criteria", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("related_creation_id", sa.Integer(), nullable=True),
        # Phase 1c 还没有 content_versions，故只保留整数引用，不创建 FK。
        sa.Column("related_version_id", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("is_manually_edited", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["meeting_id"], ["meetings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["related_creation_id"],
            ["content_creations.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_meeting_suggestions_meeting_id",
        "meeting_suggestions",
        ["meeting_id"],
    )
    op.create_index(
        "ix_meeting_suggestions_status",
        "meeting_suggestions",
        ["status"],
    )
    op.create_index(
        "ix_meeting_suggestions_priority",
        "meeting_suggestions",
        ["priority"],
    )
    op.create_index(
        "ix_meeting_suggestions_owner_id",
        "meeting_suggestions",
        ["owner_id"],
    )
    op.create_index(
        "ix_meeting_suggestions_related_version_id",
        "meeting_suggestions",
        ["related_version_id"],
    )
    op.create_index(
        "ix_meeting_suggestions_category",
        "meeting_suggestions",
        ["category"],
    )
    op.create_index(
        "ix_meeting_suggestions_meeting_status",
        "meeting_suggestions",
        ["meeting_id", "status"],
    )
    op.create_index(
        "ix_meeting_suggestions_owner_status",
        "meeting_suggestions",
        ["owner_id", "status"],
    )
    op.create_index(
        "ix_meeting_suggestions_creation",
        "meeting_suggestions",
        ["related_creation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_meeting_suggestions_creation", table_name="meeting_suggestions")
    op.drop_index("ix_meeting_suggestions_owner_status", table_name="meeting_suggestions")
    op.drop_index("ix_meeting_suggestions_meeting_status", table_name="meeting_suggestions")
    op.drop_index("ix_meeting_suggestions_category", table_name="meeting_suggestions")
    op.drop_index("ix_meeting_suggestions_related_version_id", table_name="meeting_suggestions")
    op.drop_index("ix_meeting_suggestions_owner_id", table_name="meeting_suggestions")
    op.drop_index("ix_meeting_suggestions_priority", table_name="meeting_suggestions")
    op.drop_index("ix_meeting_suggestions_status", table_name="meeting_suggestions")
    op.drop_index("ix_meeting_suggestions_meeting_id", table_name="meeting_suggestions")
    op.drop_table("meeting_suggestions")
    op.drop_index("ix_meetings_created_by_meeting_at", table_name="meetings")
    op.drop_index("ix_meetings_status_meeting_at", table_name="meetings")
    op.drop_index("ix_meetings_created_by", table_name="meetings")
    op.drop_index("ix_meetings_status", table_name="meetings")
    op.drop_index("ix_meetings_meeting_at", table_name="meetings")
    op.drop_table("meetings")

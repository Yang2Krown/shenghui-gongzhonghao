"""add methodology synthesis for meeting notes.

Revision ID: 20260811_methodology
Revises: 20260811_phase1b
Create Date: 2026-08-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260811_methodology"
down_revision: Union[str, None] = "20260811_phase1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meeting_syntheses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("methodology", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("checklist", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("decisions", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("disagreements", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("open_questions", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("follow_ups", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column(
            "parse_status",
            sa.String(length=20),
            server_default="parsed",
            nullable=False,
        ),
        sa.Column(
            "is_manually_edited",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["meeting_id"],
            ["meetings.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meeting_id", name="uq_meeting_syntheses_meeting_id"),
    )
    op.create_index(
        "ix_meeting_syntheses_parse_status",
        "meeting_syntheses",
        ["parse_status"],
    )
    op.create_index(
        "ix_meeting_syntheses_updated_at",
        "meeting_syntheses",
        ["updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_meeting_syntheses_updated_at", table_name="meeting_syntheses")
    op.drop_index("ix_meeting_syntheses_parse_status", table_name="meeting_syntheses")
    op.drop_table("meeting_syntheses")

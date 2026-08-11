"""add cross-meeting semantic methodology clusters and sources.

Revision ID: 20260811_meeting_dedup
Revises: 20260811_methodology
Create Date: 2026-08-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260811_meeting_dedup"
down_revision: Union[str, None] = "20260811_methodology"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meeting_methodology_clusters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("section", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("rule", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("example", sa.Text(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("canonical_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("source_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("is_manually_edited", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_meeting_methodology_clusters_scope",
        "meeting_methodology_clusters",
        ["section", "category", "status"],
    )
    op.create_index(
        "ix_meeting_methodology_clusters_fingerprint",
        "meeting_methodology_clusters",
        ["section", "category", "canonical_fingerprint"],
    )
    op.create_index(
        "ix_meeting_methodology_clusters_category",
        "meeting_methodology_clusters",
        ["category"],
    )
    op.create_index(
        "ix_meeting_methodology_clusters_status",
        "meeting_methodology_clusters",
        ["status"],
    )

    op.create_table(
        "meeting_methodology_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(length=20), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("item", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("similarity", sa.Float(), nullable=True),
        sa.Column("match_kind", sa.String(length=30), server_default="new", nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["meeting_methodology_clusters.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["meeting_id"],
            ["meetings.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "meeting_id",
            "section",
            "source_fingerprint",
            name="uq_meeting_methodology_source_item",
        ),
    )
    op.create_index(
        "ix_meeting_methodology_sources_cluster",
        "meeting_methodology_sources",
        ["cluster_id", "meeting_id"],
    )
    op.create_index(
        "ix_meeting_methodology_sources_meeting",
        "meeting_methodology_sources",
        ["meeting_id", "section"],
    )
    op.create_index(
        "ix_meeting_methodology_sources_cluster_id",
        "meeting_methodology_sources",
        ["cluster_id"],
    )
    op.create_index(
        "ix_meeting_methodology_sources_meeting_id",
        "meeting_methodology_sources",
        ["meeting_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_meeting_methodology_sources_meeting_id", table_name="meeting_methodology_sources")
    op.drop_index("ix_meeting_methodology_sources_cluster_id", table_name="meeting_methodology_sources")
    op.drop_index("ix_meeting_methodology_sources_meeting", table_name="meeting_methodology_sources")
    op.drop_index("ix_meeting_methodology_sources_cluster", table_name="meeting_methodology_sources")
    op.drop_table("meeting_methodology_sources")
    op.drop_index("ix_meeting_methodology_clusters_status", table_name="meeting_methodology_clusters")
    op.drop_index("ix_meeting_methodology_clusters_category", table_name="meeting_methodology_clusters")
    op.drop_index("ix_meeting_methodology_clusters_fingerprint", table_name="meeting_methodology_clusters")
    op.drop_index("ix_meeting_methodology_clusters_scope", table_name="meeting_methodology_clusters")
    op.drop_table("meeting_methodology_clusters")

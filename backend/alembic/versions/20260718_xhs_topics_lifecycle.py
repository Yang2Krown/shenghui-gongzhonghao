"""XHS two-wave runs, keyword lifecycle and semantic topics.

Revision ID: 20260718_xhs_topics
Revises: 20260717_xhs_agent
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.exc import NoInspectionAvailable


revision: str = "20260718_xhs_topics"
down_revision: Union[str, None] = "20260717_xhs_agent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps():
    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    try:
        inspector = inspect(bind)
        keyword_columns = {c["name"] for c in inspector.get_columns("xhs_keywords")}
        run_columns = {c["name"] for c in inspector.get_columns("xhs_keyword_runs")}
        run_uniques = {u.get("name") for u in inspector.get_unique_constraints("xhs_keyword_runs")}
        note_columns = {c["name"] for c in inspector.get_columns("xhs_notes")}
        tables = set(inspector.get_table_names())
    except NoInspectionAvailable:  # alembic --sql uses MockConnection
        keyword_columns=set();run_columns=set();note_columns=set();tables=set()
        run_uniques={"uq_xhs_keyword_run_day"}
    keyword_additions = {
        "lifecycle_status": sa.Column("lifecycle_status", sa.String(20), nullable=False, server_default="active"),
        "pinned": sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        "zero_yield_streak": sa.Column("zero_yield_streak", sa.Integer(), nullable=False, server_default="0"),
        "last_yield_count": sa.Column("last_yield_count", sa.Integer(), nullable=False, server_default="0"),
        "lifecycle_started_at": sa.Column("lifecycle_started_at", sa.DateTime()),
        "trial_started_at": sa.Column("trial_started_at", sa.DateTime()),
        "quarantine_reason": sa.Column("quarantine_reason", sa.Text()),
    }
    for name, column in keyword_additions.items():
        if name not in keyword_columns:
            op.add_column("xhs_keywords", column)
    op.execute("UPDATE xhs_keywords SET lifecycle_started_at = CURRENT_TIMESTAMP WHERE lifecycle_started_at IS NULL")

    if "wave" not in run_columns:
        op.add_column("xhs_keyword_runs", sa.Column("wave", sa.String(20), nullable=False, server_default="manual"))
    if "scheduled_for" not in run_columns:
        op.add_column("xhs_keyword_runs", sa.Column("scheduled_for", sa.DateTime()))
    if "uq_xhs_keyword_run_day" in run_uniques:
        op.drop_constraint("uq_xhs_keyword_run_day", "xhs_keyword_runs", type_="unique")
    if "uq_xhs_keyword_run_wave" not in run_uniques:
        op.create_unique_constraint("uq_xhs_keyword_run_wave", "xhs_keyword_runs", ["keyword_id", "run_date", "wave"])

    if "topic_embedding" not in note_columns:
        op.add_column("xhs_notes", sa.Column("topic_embedding", sa.JSON()))
    if "semantic_analyzed_at" not in note_columns:
        op.add_column("xhs_notes", sa.Column("semantic_analyzed_at", sa.DateTime()))

    if "xhs_semantic_topics" not in tables:
        op.create_table(
            "xhs_semantic_topics", *_timestamps(),
            sa.Column("public_id", sa.String(36), nullable=False, unique=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("summary", sa.Text()),
            sa.Column("centroid", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("first_seen_at", sa.DateTime(), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(), nullable=False),
            sa.Column("active_days", sa.Integer(), nullable=False, server_default="1"),
        )
    if "xhs_topic_members" not in tables:
        op.create_table(
            "xhs_topic_members", *_timestamps(),
            sa.Column("topic_id", sa.Integer(), sa.ForeignKey("xhs_semantic_topics.id", ondelete="CASCADE"), nullable=False),
            sa.Column("note_id", sa.Integer(), sa.ForeignKey("xhs_notes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("similarity", sa.Float(), nullable=False, server_default="0"),
            sa.Column("assigned_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("topic_id", "note_id", name="uq_xhs_topic_member"),
        )
    if "xhs_topic_snapshots" not in tables:
        op.create_table(
            "xhs_topic_snapshots", *_timestamps(),
            sa.Column("topic_id", sa.Integer(), sa.ForeignKey("xhs_semantic_topics.id", ondelete="CASCADE"), nullable=False),
            sa.Column("snapshot_date", sa.Date(), nullable=False),
            sa.Column("wave", sa.String(20), nullable=False, server_default="nightly"),
            sa.Column("snapshot_at", sa.DateTime(), nullable=False),
            sa.Column("note_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("author_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("new_notes_24h", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("new_authors_24h", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("engagement_total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("engagement_growth", sa.Float(), nullable=False, server_default="0"),
            sa.Column("fermentation_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("evidence", sa.JSON(), nullable=False, server_default="[]"),
            sa.UniqueConstraint("topic_id", "snapshot_date", "wave", name="uq_xhs_topic_snapshot_wave"),
        )
    for table, columns in {
        "xhs_keywords": ["lifecycle_status", "pinned"],
        "xhs_keyword_runs": ["wave", "scheduled_for"],
        "xhs_notes": ["semantic_analyzed_at"],
        "xhs_semantic_topics": ["public_id", "status", "first_seen_at", "last_seen_at"],
        "xhs_topic_members": ["topic_id", "note_id"],
        "xhs_topic_snapshots": ["topic_id", "snapshot_at", "fermentation_score"],
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column], if_not_exists=True)


def downgrade() -> None:
    op.drop_table("xhs_topic_snapshots")
    op.drop_table("xhs_topic_members")
    op.drop_table("xhs_semantic_topics")
    op.drop_column("xhs_notes", "semantic_analyzed_at")
    op.drop_column("xhs_notes", "topic_embedding")
    op.drop_constraint("uq_xhs_keyword_run_wave", "xhs_keyword_runs", type_="unique")
    op.create_unique_constraint("uq_xhs_keyword_run_day", "xhs_keyword_runs", ["keyword_id", "run_date"])
    op.drop_column("xhs_keyword_runs", "scheduled_for")
    op.drop_column("xhs_keyword_runs", "wave")
    for column in ("quarantine_reason", "trial_started_at", "lifecycle_started_at", "last_yield_count", "zero_yield_streak", "pinned", "lifecycle_status"):
        op.drop_column("xhs_keywords", column)

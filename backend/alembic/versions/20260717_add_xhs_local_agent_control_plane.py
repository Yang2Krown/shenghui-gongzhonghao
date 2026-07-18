"""add xhs local agent control plane

Revision ID: 20260717_xhs_agent
Revises: 20260716_xhs_materials
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260717_xhs_agent"
down_revision: Union[str, None] = "20260716_xhs_materials"
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
    existing_tables = set(inspect(bind).get_table_names())
    if "xhs_collector_devices" not in existing_tables:
        op.create_table(
        "xhs_collector_devices", *_timestamps(),
        sa.Column("public_id", sa.String(36), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("platform", sa.String(40), nullable=False, server_default="macos"),
        sa.Column("agent_version", sa.String(40)),
        sa.Column("cookie_status", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("last_seen_at", sa.DateTime()),
        sa.Column("last_connected_at", sa.DateTime()),
        sa.Column("last_disconnected_at", sa.DateTime()),
        sa.Column("current_status", sa.String(30), nullable=False, server_default="offline"),
        sa.Column("current_keyword", sa.String(120)),
        sa.Column("last_error", sa.Text()),
        sa.Column("schedule_config", sa.JSON(), nullable=False, server_default="{}"),
        )
        existing_tables.add("xhs_collector_devices")
    if "xhs_agent_pairings" not in existing_tables:
        op.create_table(
        "xhs_agent_pairings", *_timestamps(),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime()),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("xhs_collector_devices.id", ondelete="SET NULL")),
        )
        existing_tables.add("xhs_agent_pairings")
    if "xhs_agent_commands" not in existing_tables:
        op.create_table(
        "xhs_agent_commands", *_timestamps(),
        sa.Column("public_id", sa.String(36), nullable=False, unique=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("xhs_collector_devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("command_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("delivered_at", sa.DateTime()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("result", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text()),
        )
        existing_tables.add("xhs_agent_commands")
    if "xhs_agent_batches" not in existing_tables:
        op.create_table(
        "xhs_agent_batches", *_timestamps(),
        sa.Column("public_id", sa.String(36), nullable=False, unique=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("xhs_collector_devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("command_id", sa.Integer(), sa.ForeignKey("xhs_agent_commands.id", ondelete="SET NULL")),
        sa.Column("local_batch_key", sa.String(120), nullable=False),
        sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="running"),
        sa.Column("schedule_date", sa.Date(), nullable=False),
        sa.Column("schedule_group", sa.Integer()),
        sa.Column("total_keywords", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_keywords", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_keywords", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_keyword_id", sa.Integer(), sa.ForeignKey("xhs_keywords.id", ondelete="SET NULL")),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("last_progress_at", sa.DateTime()),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("device_id", "local_batch_key", name="uq_xhs_agent_batch_device_local"),
        )
        existing_tables.add("xhs_agent_batches")
    run_columns = {column["name"] for column in inspect(bind).get_columns("xhs_keyword_runs")}
    if "run_source" not in run_columns:
        op.add_column("xhs_keyword_runs", sa.Column("run_source", sa.String(30), nullable=False, server_default="server_cli"))
    if "agent_batch_id" not in run_columns:
        op.add_column("xhs_keyword_runs", sa.Column("agent_batch_id", sa.Integer(), nullable=True))
    run_foreign_keys = {foreign_key.get("name") for foreign_key in inspect(bind).get_foreign_keys("xhs_keyword_runs")}
    if "fk_xhs_keyword_runs_agent_batch" not in run_foreign_keys:
        op.create_foreign_key("fk_xhs_keyword_runs_agent_batch", "xhs_keyword_runs", "xhs_agent_batches", ["agent_batch_id"], ["id"], ondelete="SET NULL")
    if "xhs_agent_uploads" not in existing_tables:
        op.create_table(
        "xhs_agent_uploads", *_timestamps(),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("xhs_agent_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("keyword_id", sa.Integer(), sa.ForeignKey("xhs_keywords.id", ondelete="SET NULL")),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("xhs_keyword_runs.id", ondelete="SET NULL")),
        sa.Column("idempotency_key", sa.String(160), nullable=False, unique=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="received"),
        sa.Column("raw_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejection_counts", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text()),
        )
        existing_tables.add("xhs_agent_uploads")
    indexes = {
        "xhs_collector_devices": ["public_id", "enabled", "cookie_status", "last_seen_at", "current_status"],
        "xhs_agent_pairings": ["created_by_user_id", "expires_at", "device_id"],
        "xhs_agent_commands": ["public_id", "device_id", "command_type", "status", "requested_by_user_id", "expires_at"],
        "xhs_agent_batches": ["public_id", "device_id", "command_id", "mode", "status", "schedule_date", "last_progress_at"],
        "xhs_agent_uploads": ["batch_id", "keyword_id", "run_id", "status"],
        "xhs_keyword_runs": ["run_source", "agent_batch_id"],
    }
    for table, columns in indexes.items():
        existing_indexes = {index["name"] for index in inspect(bind).get_indexes(table)}
        for column in columns:
            index_name = f"ix_{table}_{column}"
            if index_name not in existing_indexes:
                op.create_index(index_name, table, [column])
    op.alter_column("xhs_keyword_runs", "run_source", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_xhs_keyword_runs_agent_batch_id", table_name="xhs_keyword_runs")
    op.drop_index("ix_xhs_keyword_runs_run_source", table_name="xhs_keyword_runs")
    op.drop_table("xhs_agent_uploads")
    op.drop_constraint("fk_xhs_keyword_runs_agent_batch", "xhs_keyword_runs", type_="foreignkey")
    op.drop_column("xhs_keyword_runs", "agent_batch_id")
    op.drop_column("xhs_keyword_runs", "run_source")
    op.drop_table("xhs_agent_batches")
    op.drop_table("xhs_agent_commands")
    op.drop_table("xhs_agent_pairings")
    op.drop_table("xhs_collector_devices")

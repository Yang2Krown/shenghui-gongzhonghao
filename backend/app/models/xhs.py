"""小红书关键词素材库模型（封面与头像只保存远程 URL，不转存 OSS）。"""

import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from app.db.base import BaseModel, JSONField


class XhsKeyword(BaseModel):
    __tablename__ = "xhs_keywords"

    keyword = Column(String(120), nullable=False)
    normalized_keyword = Column(String(120), nullable=False, unique=True, index=True)
    keyword_type = Column(String(20), nullable=False, default="base", index=True)
    schedule_group = Column(Integer, nullable=True, index=True)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    derived_evidence = Column(JSONField, nullable=False, default=dict)
    cooldown_until = Column(Date, nullable=True, index=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    lifecycle_status = Column(String(20), nullable=False, default="active", index=True)
    pinned = Column(Boolean, nullable=False, default=False, index=True)
    zero_yield_streak = Column(Integer, nullable=False, default=0)
    last_yield_count = Column(Integer, nullable=False, default=0)
    lifecycle_started_at = Column(DateTime, nullable=True)
    trial_started_at = Column(DateTime, nullable=True)
    quarantine_reason = Column(Text, nullable=True)


class XhsKeywordRun(BaseModel):
    __tablename__ = "xhs_keyword_runs"

    keyword_id = Column(Integer, ForeignKey("xhs_keywords.id", ondelete="CASCADE"), nullable=False, index=True)
    run_date = Column(Date, nullable=False, index=True)
    status = Column(String(30), nullable=False, default="pending", index=True)
    tikhub_status = Column(String(30), nullable=False, default="pending")
    cli_status = Column(String(30), nullable=False, default="pending")
    tikhub_raw_count = Column(Integer, nullable=False, default=0)
    cli_raw_count = Column(Integer, nullable=False, default=0)
    merged_count = Column(Integer, nullable=False, default=0)
    within_week_count = Column(Integer, nullable=False, default=0)
    eligible_like_count = Column(Integer, nullable=False, default=0)
    filtered_count = Column(Integer, nullable=False, default=0)
    final_count = Column(Integer, nullable=False, default=0)
    displayable_count = Column(Integer, nullable=False, default=0)
    paid_call_count = Column(Integer, nullable=False, default=0)
    rejection_counts = Column(JSONField, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    run_source = Column(String(30), nullable=False, default="server_cli", index=True)
    agent_batch_id = Column(Integer, ForeignKey("xhs_agent_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    wave = Column(String(20), nullable=False, default="manual", index=True)
    scheduled_for = Column(DateTime, nullable=True, index=True)

    __table_args__ = (UniqueConstraint("keyword_id", "run_date", "wave", name="uq_xhs_keyword_run_wave"),)


class XhsNote(BaseModel):
    __tablename__ = "xhs_notes"

    note_id = Column(String(100), nullable=False, unique=True, index=True)
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True, index=True)
    note_type = Column(String(20), nullable=True, index=True)
    author_id = Column(String(100), nullable=True, index=True)
    author_nickname = Column(String(200), nullable=True)
    author_bio = Column(Text, nullable=True)
    avatar_url = Column(String(2000), nullable=True)
    cover_url = Column(String(2000), nullable=True)
    native_tags = Column(JSONField, nullable=False, default=list)
    ai_summary = Column(Text, nullable=True)
    ai_topics = Column(JSONField, nullable=False, default=list)
    like_count = Column(Integer, nullable=True, index=True)
    collect_count = Column(Integer, nullable=True)
    comment_count = Column(Integer, nullable=True)
    share_count = Column(Integer, nullable=True)
    view_count = Column(Integer, nullable=True)
    stable_url = Column(String(1000), nullable=False)
    latest_xsec_url = Column(String(2000), nullable=True)
    first_discovered_at = Column(DateTime, nullable=False)
    last_discovered_at = Column(DateTime, nullable=False, index=True)
    detail_status = Column(String(30), nullable=False, default="discovered", index=True)
    media_status = Column(String(30), nullable=False, default="remote_ok", index=True)
    quality_status = Column(String(30), nullable=False, default="pending", index=True)
    comprehensive_score = Column(Float, nullable=False, default=0, index=True)
    raw_info_id = Column(Integer, ForeignKey("raw_infos.id", ondelete="SET NULL"), nullable=True, index=True)
    source_payload = Column(JSONField, nullable=False, default=dict)
    topic_embedding = Column(JSONField, nullable=True)
    semantic_analyzed_at = Column(DateTime, nullable=True, index=True)

    __table_args__ = (
        Index("ix_xhs_notes_public", "quality_status", "published_at", "like_count"),
    )


class XhsNoteDiscovery(BaseModel):
    __tablename__ = "xhs_note_discoveries"

    note_id = Column(Integer, ForeignKey("xhs_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    keyword_id = Column(Integer, ForeignKey("xhs_keywords.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id = Column(Integer, ForeignKey("xhs_keyword_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(30), nullable=False, index=True)
    provider_rank = Column(Integer, nullable=True)
    discovered_at = Column(DateTime, nullable=False)

    __table_args__ = (UniqueConstraint("run_id", "note_id", "provider", name="uq_xhs_discovery_run_note_src"),)


class XhsProviderCall(BaseModel):
    __tablename__ = "xhs_provider_calls"

    provider = Column(String(30), nullable=False, index=True)
    operation = Column(String(30), nullable=False, index=True)
    run_id = Column(Integer, ForeignKey("xhs_keyword_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    note_identity = Column(String(100), nullable=True, index=True)
    status = Column(String(30), nullable=False, index=True)
    is_paid = Column(Boolean, nullable=False, default=False)
    request_count = Column(Integer, nullable=False, default=1)
    latency_ms = Column(Integer, nullable=True)
    estimated_cost = Column(Float, nullable=False, default=0)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_json = Column(JSONField, nullable=False, default=dict)


class XhsEngagementSnapshot(BaseModel):
    __tablename__ = "xhs_engagement_snapshots"

    note_id = Column(Integer, ForeignKey("xhs_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    like_count = Column(Integer, nullable=True)
    collect_count = Column(Integer, nullable=True)
    comment_count = Column(Integer, nullable=True)
    share_count = Column(Integer, nullable=True)
    view_count = Column(Integer, nullable=True)

    __table_args__ = (UniqueConstraint("note_id", "snapshot_date", name="uq_xhs_note_snapshot_day"),)


class XhsSemanticTopic(BaseModel):
    """由笔记正文语义形成的话题；名称不等同于采集关键词。"""
    __tablename__ = "xhs_semantic_topics"

    public_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)
    summary = Column(Text, nullable=True)
    centroid = Column(JSONField, nullable=False, default=list)
    status = Column(String(20), nullable=False, default="active", index=True)
    first_seen_at = Column(DateTime, nullable=False, index=True)
    last_seen_at = Column(DateTime, nullable=False, index=True)
    active_days = Column(Integer, nullable=False, default=1)


class XhsTopicMember(BaseModel):
    __tablename__ = "xhs_topic_members"

    topic_id = Column(Integer, ForeignKey("xhs_semantic_topics.id", ondelete="CASCADE"), nullable=False, index=True)
    note_id = Column(Integer, ForeignKey("xhs_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    similarity = Column(Float, nullable=False, default=0)
    assigned_at = Column(DateTime, nullable=False)

    __table_args__ = (UniqueConstraint("topic_id", "note_id", name="uq_xhs_topic_member"),)


class XhsTopicSnapshot(BaseModel):
    __tablename__ = "xhs_topic_snapshots"

    topic_id = Column(Integer, ForeignKey("xhs_semantic_topics.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    wave = Column(String(20), nullable=False, default="nightly")
    snapshot_at = Column(DateTime, nullable=False, index=True)
    note_count = Column(Integer, nullable=False, default=0)
    author_count = Column(Integer, nullable=False, default=0)
    new_notes_24h = Column(Integer, nullable=False, default=0)
    new_authors_24h = Column(Integer, nullable=False, default=0)
    engagement_total = Column(Integer, nullable=False, default=0)
    engagement_growth = Column(Float, nullable=False, default=0)
    fermentation_score = Column(Float, nullable=False, default=0, index=True)
    evidence = Column(JSONField, nullable=False, default=list)

    __table_args__ = (UniqueConstraint("topic_id", "snapshot_date", "wave", name="uq_xhs_topic_snapshot_wave"),)


class XhsDailyQuota(BaseModel):
    __tablename__ = "xhs_daily_quotas"

    quota_date = Column(Date, nullable=False, unique=True, index=True)
    limit_count = Column(Integer, nullable=False, default=100)
    used_count = Column(Integer, nullable=False, default=0)
    reserved_search_count = Column(Integer, nullable=False, default=0)


class XhsImageFailureReport(BaseModel):
    __tablename__ = "xhs_image_failure_reports"

    note_id = Column(Integer, ForeignKey("xhs_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    image_kind = Column(String(20), nullable=False, default="cover")
    failed_url = Column(String(2000), nullable=False)
    reporter_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    failure_count = Column(Integer, nullable=False, default=1)
    last_failed_at = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False, default="open", index=True)

    __table_args__ = (UniqueConstraint("note_id", "image_kind", "failed_url", name="uq_xhs_image_failure"),)


class XhsCollectorDevice(BaseModel):
    """已绑定的本地采集节点；只保存 Token 哈希，不保存 Cookie。"""
    __tablename__ = "xhs_collector_devices"

    public_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(120), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    platform = Column(String(40), nullable=False, default="macos")
    agent_version = Column(String(40), nullable=True)
    cookie_status = Column(String(30), nullable=False, default="unknown", index=True)
    last_seen_at = Column(DateTime, nullable=True, index=True)
    last_connected_at = Column(DateTime, nullable=True)
    last_disconnected_at = Column(DateTime, nullable=True)
    current_status = Column(String(30), nullable=False, default="offline", index=True)
    current_keyword = Column(String(120), nullable=True)
    last_error = Column(Text, nullable=True)
    schedule_config = Column(JSONField, nullable=False, default=dict)


class XhsAgentPairing(BaseModel):
    __tablename__ = "xhs_agent_pairings"

    code_hash = Column(String(64), nullable=False, unique=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)
    device_id = Column(Integer, ForeignKey("xhs_collector_devices.id", ondelete="SET NULL"), nullable=True, index=True)


class XhsAgentCommand(BaseModel):
    __tablename__ = "xhs_agent_commands"

    public_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(Integer, ForeignKey("xhs_collector_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    command_type = Column(String(30), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="queued", index=True)
    payload = Column(JSONField, nullable=False, default=dict)
    requested_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    delivered_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    result = Column(JSONField, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)


class XhsAgentBatch(BaseModel):
    __tablename__ = "xhs_agent_batches"

    public_id = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(Integer, ForeignKey("xhs_collector_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    command_id = Column(Integer, ForeignKey("xhs_agent_commands.id", ondelete="SET NULL"), nullable=True, index=True)
    local_batch_key = Column(String(120), nullable=False)
    mode = Column(String(30), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="running", index=True)
    schedule_date = Column(Date, nullable=False, index=True)
    schedule_group = Column(Integer, nullable=True)
    total_keywords = Column(Integer, nullable=False, default=0)
    completed_keywords = Column(Integer, nullable=False, default=0)
    failed_keywords = Column(Integer, nullable=False, default=0)
    current_keyword_id = Column(Integer, ForeignKey("xhs_keywords.id", ondelete="SET NULL"), nullable=True)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    last_progress_at = Column(DateTime, nullable=True, index=True)
    metadata_json = Column(JSONField, nullable=False, default=dict)

    __table_args__ = (UniqueConstraint("device_id", "local_batch_key", name="uq_xhs_agent_batch_device_local"),)


class XhsAgentUpload(BaseModel):
    __tablename__ = "xhs_agent_uploads"

    batch_id = Column(Integer, ForeignKey("xhs_agent_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    keyword_id = Column(Integer, ForeignKey("xhs_keywords.id", ondelete="SET NULL"), nullable=True, index=True)
    run_id = Column(Integer, ForeignKey("xhs_keyword_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    idempotency_key = Column(String(160), nullable=False, unique=True)
    payload_hash = Column(String(64), nullable=False)
    status = Column(String(30), nullable=False, default="received", index=True)
    raw_count = Column(Integer, nullable=False, default=0)
    accepted_count = Column(Integer, nullable=False, default=0)
    rejection_counts = Column(JSONField, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)


class XhsTopicBoard(BaseModel):
    """分析任务生成的「今日热榜 + 持续发酵」看板快照；页面读最新一版，不实时计算。"""
    __tablename__ = "xhs_topic_boards"

    edition_date = Column(Date, nullable=False, index=True)
    wave = Column(String(20), nullable=False, default="manual")
    payload = Column(JSONField, nullable=False, default=dict)

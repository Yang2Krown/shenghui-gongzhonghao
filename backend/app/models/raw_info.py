"""原始信息表：抓取层的统一落点。

每个 adapter（rss/web/github/exa_wechat/...）抓回来的内容都写到这里。
后续 preprocess 脚本会读 RawInfo → 去重/聚类/类型标注/要素提取 → InfoCluster。
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.db.base import BaseModel, JSONField


# preprocess 状态机
RAW_STATE_PENDING = "pending"          # 刚抓回来
RAW_STATE_DEDUPED = "deduped"          # 已去重
RAW_STATE_CLUSTERED = "clustered"      # 已分配到 InfoCluster
RAW_STATE_SKIPPED = "skipped"          # 被预处理判定为不可用


class RawInfo(BaseModel):
    """单条原始信息（抓取层落点，不做语义处理）。"""
    __tablename__ = "raw_infos"

    source_registry_id = Column(Integer, ForeignKey("source_registry.id"), nullable=False, index=True)
    source_account_id = Column(Integer, ForeignKey("source_accounts.id"), nullable=True, index=True)

    # 抓取层基本字段
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=False, unique=True, index=True)
    author = Column(String(200), nullable=True)
    summary = Column(Text, nullable=True)                              # 摘要 / 卡片文本
    content = Column(Text, nullable=True)                              # 全文（adapter 可选填，按需）
    published_at = Column(DateTime, nullable=True, index=True)
    scraped_at = Column(DateTime, nullable=True, index=True)

    # 互动 / 热度数据（不同来源字段不同，统一放进来）
    engagement = Column(JSONField, default=dict)                            # {read, like, comment, share, ...}
    extras = Column(JSONField, default=dict)                                # adapter 各自的原始 payload 残留

    # 预处理状态
    state = Column(String(20), default=RAW_STATE_PENDING, index=True)
    info_cluster_id = Column(Integer, ForeignKey("info_clusters.id"), nullable=True, index=True)
    dedup_hash = Column(String(64), nullable=True, index=True)         # 内容指纹（标题/URL 归一化后 hash）

    # 语义向量（用于聚类，pgvector）
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=True)

    source = relationship("SourceRegistry", back_populates="raw_infos")
    info_cluster = relationship("InfoCluster", back_populates="raw_infos")

    __table_args__ = (
        # 预处理脚本主查询：按 state + 时间扫待处理条目
        Index("ix_raw_info_state_scraped", "state", "scraped_at"),
        # 按来源 + 时间倒序拉最新（admin 调试 / API 列表）
        Index("ix_raw_info_source_published", "source_registry_id", "published_at"),
    )

    def __repr__(self):
        return f"<RawInfo(id={self.id}, title='{(self.title or '')[:40]}...')>"

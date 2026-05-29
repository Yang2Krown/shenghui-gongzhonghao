"""信息簇：预处理脚本（去重/聚类/类型标注/要素提取）的输出。

对齐《选题挖掘 Agent 设计文档》1.4 节"预处理后的信息"：
信息ID / 来源列表 / 核心标题 / 信息类型 / 要素 / 时效新鲜度 / 热度评分 / 低粉爆款标记。
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, Index
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.db.base import BaseModel, JSONField


# 信息类型（设计文档 2.3 节）
INFO_TYPE_NEWS = "资讯型"
INFO_TYPE_CASE = "实操案例型"
INFO_TYPE_OPINION = "观点分享型"
INFO_TYPE_TUTORIAL = "教程型"

# 时效新鲜度（设计文档 1.4 节）
FRESHNESS_24H = "24h"
FRESHNESS_7D = "7d"
FRESHNESS_30D = "30d"
FRESHNESS_EXPIRED = "expired"


# info_type → 公众号创作价值权重（路人甲TM 偏好：工具实操 > 教程 > 观点 > 资讯）
# 同样的 heat_score，教程型卡片排序时是资讯型的 3.6 倍
INFO_TYPE_WEIGHT = {
    INFO_TYPE_TUTORIAL: 1.8,    # 教程型 — 最适合公众号长内容
    INFO_TYPE_CASE: 1.6,        # 实操案例型 — 工具实战分享
    INFO_TYPE_OPINION: 1.1,     # 观点分享型 — 微微加权
    INFO_TYPE_NEWS: 0.5,        # 资讯型 — 压后（不删，可筛）
}


class InfoCluster(BaseModel):
    """信息簇（多条 RawInfo 聚合）。Agent A 的输入单元。"""
    __tablename__ = "info_clusters"

    # 核心信息
    core_title = Column(String(500), nullable=False)                   # 原文标题（可能英文）
    core_title_zh = Column(String(500), nullable=True)                 # 中文翻译（英文 cluster 才会有）
    latest_title = Column(String(500), nullable=True)                  # 最新一条 raw 的标题（合并后更新）
    summary = Column(Text, nullable=True)                              # 簇级摘要（多源合并后的整体描述）
    summary_zh = Column(Text, nullable=True)                           # 摘要中文翻译
    info_type = Column(String(30), nullable=True, index=True)          # 见 INFO_TYPE_*
    direction = Column(String(50), nullable=True, index=True)          # 大模型 / Coding Agent / AI视频 / ...

    # 要素（设计文档 1.4 节）
    elements = Column(JSONField, default=dict)                              # {主体, 动作, 对象, 亮点, 争议, 数据}

    # 来源聚合
    source_count = Column(Integer, default=1)                          # 来源条数
    source_urls = Column(JSONField, default=list)                           # 所有 RawInfo URL 快照

    # 热度 / 时效
    freshness = Column(String(20), nullable=True, index=True)          # 24h/7d/30d/expired
    heat_score = Column(Float, default=0.0, index=True)                # 0-10
    low_fan_hit = Column(Boolean, default=False)                       # 低粉爆款标记
    published_at = Column(DateTime, nullable=True)

    # 处理状态
    mined = Column(Boolean, default=False, index=True)                 # 是否已被 Agent A/B 处理过
    is_ai_relevant = Column(Boolean, default=True, index=True)         # 预处理时打的 AI 相关性标，列表 API 用它做 SQL 层过滤

    # 簇中心向量（簇内 RawInfo embedding 的平均）：用于"新条目找最近簇"
    centroid = Column(Vector(settings.EMBEDDING_DIM), nullable=True)

    raw_infos = relationship("RawInfo", back_populates="info_cluster")
    candidates = relationship("TopicCandidate", back_populates="info_cluster", cascade="all, delete-orphan")

    __table_args__ = (
        # Agent A 主查询：拉"未挖掘过"且"还新鲜"的簇
        Index("ix_cluster_mined_freshness", "mined", "freshness"),
        Index("ix_cluster_direction_heat", "direction", "heat_score"),
    )

    def __repr__(self):
        return f"<InfoCluster(id={self.id}, type='{self.info_type}', title='{(self.core_title or '')[:30]}...')>"

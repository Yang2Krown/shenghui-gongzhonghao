"""每日选题清单：下游全局排序脚本（跨簇去重 + 方向多样性 + Top N）的输出。

不在选题挖掘 Agent 范围内，但需要这张表给前端 / 大纲 Agent 消费。
"""

from sqlalchemy import Column, Integer, String, Date, ForeignKey, Float
from sqlalchemy.orm import relationship

from app.db.base import BaseModel, JSONField


class DailyTopicList(BaseModel):
    """单天的 Top N 选题清单（一行 = 一天）。"""
    __tablename__ = "daily_topic_lists"

    list_date = Column(Date, nullable=False, unique=True, index=True)
    top_n = Column(Integer, default=10)
    items = Column(JSONField, default=list)                                 # [{candidate_id, rank, direction, score, ...}]
    direction_distribution = Column(JSONField, default=dict)                # {大模型: 3, Coding Agent: 2, ...}
    notes = Column(JSONField, default=dict)                                 # 排序脚本输出的附加说明

    def __repr__(self):
        return f"<DailyTopicList(date={self.list_date}, top_n={self.top_n})>"


class DailyTopicListItem(BaseModel):
    """清单条目（normalized 表，便于按 candidate 反查"上过哪天的榜"）。"""
    __tablename__ = "daily_topic_list_items"

    list_id = Column(Integer, ForeignKey("daily_topic_lists.id"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("topic_candidates.id"), nullable=False, index=True)
    rank = Column(Integer, nullable=False)
    score_snapshot = Column(Float, nullable=True)

    def __repr__(self):
        return f"<DailyTopicListItem(list={self.list_id}, candidate={self.candidate_id}, rank={self.rank})>"

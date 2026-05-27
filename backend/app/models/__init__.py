from app.models.user import User, UserProfile
from app.models.topic import Topic, TopicCollection
from app.models.creation import ContentCreation
from app.models.style import StyleProfile, ArticleForAnalysis

# v2.0 选题挖掘 pipeline 新增模型
from app.models.source_registry import SourceRegistry, SourceAccount
from app.models.raw_info import RawInfo
from app.models.info_cluster import InfoCluster
from app.models.topic_candidate import TopicCandidate, PersonaReview, CandidateScore
from app.models.daily_topic_list import DailyTopicList, DailyTopicListItem

# 生成记录
from app.models.generation_record import GenerationRecord

# v3.0 大纲生成 pipeline 新增模型
from app.models.outline import (
    Outline,
    OutlineCandidate,
    OutlineReview,
    OutlineCriticism,
    OutlineInspection,
)

__all__ = [
    # 旧模型（过渡期保留）
    "User",
    "UserProfile",
    "Topic",
    "TopicCollection",
    "ContentCreation",
    "StyleProfile",
    "ArticleForAnalysis",
    # v2.0 选题 pipeline
    "SourceRegistry",
    "SourceAccount",
    "RawInfo",
    "InfoCluster",
    "TopicCandidate",
    "PersonaReview",
    "CandidateScore",
    "DailyTopicList",
    "DailyTopicListItem",
    # 生成记录
    "GenerationRecord",
    # v3.0 大纲 pipeline
    "Outline",
    "OutlineCandidate",
    "OutlineReview",
    "OutlineCriticism",
    "OutlineInspection",
]
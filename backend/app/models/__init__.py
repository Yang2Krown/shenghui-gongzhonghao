from app.models.user import User, UserProfile
from app.models.topic import Topic, TopicCollection
from app.models.creation import ContentCreation
from app.models.creation_publication import CreationPublication
from app.models.style import StyleProfile, ArticleForAnalysis

# v2.0 选题挖掘 pipeline 新增模型
from app.models.source_registry import SourceRegistry, SourceAccount
from app.models.raw_info import RawInfo
from app.models.info_cluster import InfoCluster
from app.models.topic_candidate import TopicCandidate, PersonaReview, CandidateScore

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

# 微信公众号账号管理
from app.models.wechat_account import WechatAccount

# 飞书授权绑定（商单 brief 接入）
from app.models.feishu_auth import FeishuAuth

# P0 团队协作底座
from app.models.employee_profile import EmployeeProfile
from app.models.article_member import ArticleMember
from app.models.meeting import Meeting, MeetingSuggestion, MeetingSynthesis
from app.models.meeting_methodology import MeetingMethodologyCluster, MeetingMethodologySource
from app.models.content_version import ContentVersion, ExperienceCard
from app.models.article_review import ArticleReview, ArticleReviewComment

# 积分系统
from app.models.credit import UserCredit, CreditTransaction, CreditPackage

# 支付订单
from app.models.payment import PaymentOrder

# 管理员后台监测
from app.models.monitoring import MonitoringAlert, MonitoringSnapshot

# 管理员审计
from app.models.admin_audit import AdminAuditLog
from app.models.system_announcement import SystemAnnouncement, SystemAnnouncementDismissal

# API 请求监测
from app.models.api_request_log import ApiRequestLog

# LLM 调用成本监测
from app.models.llm_monitoring import LlmCallLog, LlmModelPricing
from app.models.celery_task_run import CeleryTaskRun

# 课程资料
from app.models.course import CourseChapter
from app.models.xhs import (
    XhsAgentBatch, XhsAgentCommand, XhsAgentPairing, XhsAgentUpload,
    XhsCollectorDevice, XhsDailyQuota, XhsEngagementSnapshot,
    XhsImageFailureReport, XhsKeyword, XhsKeywordRun, XhsNote,
    XhsNoteDiscovery, XhsProviderCall, XhsSemanticTopic, XhsTopicMember,
    XhsTopicSnapshot,
)

__all__ = [
    # 旧模型（过渡期保留）
    "User",
    "UserProfile",
    "Topic",
    "TopicCollection",
    "ContentCreation",
    "CreationPublication",
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
    # 生成记录
    "GenerationRecord",
    # v3.0 大纲 pipeline
    "Outline",
    "OutlineCandidate",
    "OutlineReview",
    "OutlineCriticism",
    "OutlineInspection",
    # 微信公众号账号
    "WechatAccount",
    # 飞书授权绑定
    "FeishuAuth",
    # P0 团队协作底座
    "EmployeeProfile",
    "ArticleMember",
    "Meeting",
    "MeetingSuggestion",
    "MeetingSynthesis",
    "MeetingMethodologyCluster",
    "MeetingMethodologySource",
    "ContentVersion",
    "ExperienceCard",
    "ArticleReview",
    "ArticleReviewComment",
    # 积分系统
    "UserCredit",
    "CreditTransaction",
    "CreditPackage",
    "PaymentOrder",
    "MonitoringSnapshot",
    "MonitoringAlert",
    "AdminAuditLog",
    "SystemAnnouncement",
    "SystemAnnouncementDismissal",
    "ApiRequestLog",
    "LlmCallLog",
    "LlmModelPricing",
    "CeleryTaskRun",
    # 课程资料
    "CourseChapter",
    "XhsKeyword", "XhsKeywordRun", "XhsNote", "XhsNoteDiscovery",
    "XhsProviderCall", "XhsEngagementSnapshot", "XhsDailyQuota", "XhsImageFailureReport",
]

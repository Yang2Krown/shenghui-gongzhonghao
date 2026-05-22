"""信息源注册表 + 账号级订阅表。

把 AI选题信息源.xlsx（站点/平台）和 关注博主整理_AI信息源.xlsx（X / 公众号 账号）
落进数据库。后续加源/改权重/停用都是改数据行，不再硬编码到 scraper_service。
"""

from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.db.base import BaseModel, JSONField


# source_type 取值（运行期校验，不用 SQL Enum）
SOURCE_TYPE_RSS = "rss"
SOURCE_TYPE_WEB = "web"
SOURCE_TYPE_GITHUB = "github"
SOURCE_TYPE_HACKERNEWS = "hackernews"
SOURCE_TYPE_REDDIT = "reddit"
SOURCE_TYPE_EXA_WECHAT = "exa_wechat"     # 公众号关键词搜索流
SOURCE_TYPE_TOPHUB = "tophub"             # 榜眼数据 API（36kr / 虎嗅 / 知乎 / 微信公众号 等热榜）
SOURCE_TYPE_GZH_EXPLOSIVE = "gzh_explosive"  # 公众号低粉爆款
SOURCE_TYPE_V2EX = "v2ex"                 # V2EX 公开 API
SOURCE_TYPE_REDDIT = "reddit"             # Reddit 公开 JSON API
SOURCE_TYPE_XHS_DAILY = "xhs_daily"       # 小红书每日爆款（SkillHub API，0 cookie）
SOURCE_TYPE_X_PLAYWRIGHT = "x_playwright" # X (Twitter) via Playwright + cookie
SOURCE_TYPE_X = "x"                        # P1
SOURCE_TYPE_WEIBO = "weibo"                # P1
SOURCE_TYPE_XHS = "xhs"                    # P1
SOURCE_TYPE_DOUYIN = "douyin"              # P2

# fetch_strategy
FETCH_STRATEGY_CRON = "cron"
FETCH_STRATEGY_ON_DEMAND = "on_demand"


class SourceRegistry(BaseModel):
    """信息源注册表（站点/平台级）。"""
    __tablename__ = "source_registry"

    name = Column(String(200), nullable=False, index=True)
    platform = Column(String(50), nullable=False, unique=True, index=True)  # 全局唯一：seed 脚本以此 upsert
    source_type = Column(String(30), nullable=False, index=True)       # 见 SOURCE_TYPE_*
    url = Column(String(1000), nullable=True)                          # RSS feed url / 网页入口 / 平台 API base
    tier = Column(Integer, nullable=True)                              # 表1 的 1-7 层
    direction_tags = Column(JSONField, default=list)                        # ["大模型", "Coding Agent", ...]
    weight = Column(Integer, default=5)                                # 表3 RSS 权重 / 自定义
    requires_auth = Column(Boolean, default=False)
    auth_status = Column(String(20), default="ok")                     # ok / expired / missing
    fetch_strategy = Column(String(20), default=FETCH_STRATEGY_CRON)
    fetch_config = Column(JSONField, default=dict)                          # adapter 自定义参数（关键词列表 / limit / 域名过滤等）
    enabled = Column(Boolean, default=True, index=True)
    description = Column(Text, nullable=True)
    last_fetched_at = Column(String(40), nullable=True)                # ISO 字符串，避免 timezone 问题；正式查询用 RawInfo.scraped_at

    accounts = relationship("SourceAccount", back_populates="source", cascade="all, delete-orphan")
    raw_infos = relationship("RawInfo", back_populates="source")

    def __repr__(self):
        return f"<SourceRegistry(id={self.id}, name='{self.name}', type='{self.source_type}')>"


class SourceAccount(BaseModel):
    """账号级订阅（重点博主清单）：X / 公众号 / 小红书账号等。"""
    __tablename__ = "source_accounts"

    source_registry_id = Column(Integer, ForeignKey("source_registry.id"), nullable=False, index=True)
    handle = Column(String(200), nullable=True, index=True)            # @xxx / 公众号 ID
    display_name = Column(String(200), nullable=False)                 # 名称
    verified = Column(String(20), nullable=True)                       # 是 / 否 / 金标
    category = Column(String(100), nullable=True)                      # 领域分类（AI研究/安全、AI图像/视频/设计 等）
    description = Column(Text, nullable=True)                          # 简介/定位
    suitable_for = Column(Text, nullable=True)                         # 适合参考什么
    priority = Column(String(50), nullable=True)                       # 每日必看 / 深度研究 / AI编程 / 中文内容参考
    fans_count = Column(Integer, nullable=True)
    note = Column(String(200), nullable=True)                          # 备注/来源（"截图1" 等）
    enabled = Column(Boolean, default=True, index=True)

    source = relationship("SourceRegistry", back_populates="accounts")

    __table_args__ = (
        # 同一 source 下，handle + display_name 组合唯一；handle 可空时退化为 display_name 唯一
        UniqueConstraint("source_registry_id", "handle", "display_name", name="uq_account_per_source"),
        Index("ix_account_priority", "priority"),
    )

    def __repr__(self):
        return f"<SourceAccount(id={self.id}, handle='{self.handle}', name='{self.display_name}')>"

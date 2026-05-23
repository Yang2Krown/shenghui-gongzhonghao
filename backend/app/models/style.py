from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import BaseModel


class StyleProfile(BaseModel):
    """风格档案模型"""
    __tablename__ = "style_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # 风格训练结果
    version = Column(Integer, default=1)  # 版本号
    signature = Column(Text, nullable=True)  # 风格签名（3-5个关键词）
    radar = Column(JSON, default={})  # 6维雷达图数据
    traits = Column(JSON, default=[])  # 风格特征标签数组
    source_count = Column(Integer, default=0)  # 素材数量
    total_words = Column(Integer, default=0)  # 总字数
    trained_at = Column(DateTime, nullable=True)  # 最后训练时间

    # 旧字段（保留兼容）
    style_features = Column(JSON, default={})  # 风格特征
    confidence_score = Column(Float, default=0.0)  # 置信度分数
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    # 风格特征详情
    tone = Column(String(100), nullable=True)  # 语气：专业、轻松、幽默等
    language_style = Column(String(100), nullable=True)  # 语言风格：简洁、详细、文艺等
    sentence_structure = Column(String(100), nullable=True)  # 句式结构：简单、复杂、混合
    vocabulary_level = Column(String(100), nullable=True)  # 词汇水平：基础、专业、高级
    paragraph_length = Column(String(100), nullable=True)  # 段落长度：短、中、长
    use_emoji = Column(Boolean, default=False)  # 是否使用emoji
    use_questions = Column(Boolean, default=True)  # 是否使用问句
    use_statistics = Column(Boolean, default=True)  # 是否使用数据

    # 时间戳
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    user = relationship("User", back_populates="style_profiles")
    creations = relationship("ContentCreation", back_populates="style_profile")
    sources = relationship("StyleSource", back_populates="profile", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StyleProfile(id={self.id}, name='{self.name}', user_id={self.user_id})>"

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "signature": self.signature,
            "radar": self.radar,
            "traits": self.traits,
            "source_count": self.source_count,
            "total_words": self.total_words,
            "trained_at": self.trained_at.isoformat() if self.trained_at else None,
            "style_features": self.style_features,
            "confidence_score": self.confidence_score,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "tone": self.tone,
            "language_style": self.language_style,
            "sentence_structure": self.sentence_structure,
            "vocabulary_level": self.vocabulary_level,
            "paragraph_length": self.paragraph_length,
            "use_emoji": self.use_emoji,
            "use_questions": self.use_questions,
            "use_statistics": self.use_statistics,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class StyleSource(BaseModel):
    """训练素材模型"""
    __tablename__ = "style_sources"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    profile_id = Column(Integer, ForeignKey("style_profiles.id"), nullable=True)
    title = Column(String(500), nullable=True)
    content_type = Column(String(50), default="text")  # text, link, file, xhs, gzh
    url = Column(String(1000), nullable=True)
    raw_text = Column(Text, nullable=True)
    preview = Column(Text, nullable=True)  # 内容预览（前200字）
    word_count = Column(Integer, default=0)

    # 时间戳
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # 关系
    user = relationship("User", back_populates="style_sources")
    profile = relationship("StyleProfile", back_populates="sources")

    def __repr__(self):
        return f"<StyleSource(id={self.id}, title='{self.title}', user_id={self.user_id})>"

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "profile_id": self.profile_id,
            "title": self.title,
            "contentType": self.content_type,
            "url": self.url,
            "rawText": self.raw_text,
            "preview": self.preview,
            "wordCount": self.word_count,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class ArticleForAnalysis(BaseModel):
    """分析文章模型"""
    __tablename__ = "articles_for_analysis"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    original_url = Column(String(1000), nullable=True)
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=False)
    platform = Column(String(50), nullable=True)  # 来源平台
    author = Column(String(200), nullable=True)
    published_at = Column(DateTime, nullable=True)
    word_count = Column(Integer, default=0)
    is_processed = Column(Boolean, default=False)
    processing_status = Column(String(20), default="pending")  # pending, processing, completed, failed

    # 时间戳
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    user = relationship("User", back_populates="articles")

    def __repr__(self):
        return f"<ArticleForAnalysis(id={self.id}, title='{self.title[:50]}...', user_id={self.user_id})>"

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "original_url": self.original_url,
            "title": self.title,
            "content": self.content[:500] + "..." if len(self.content) > 500 else self.content,
            "platform": self.platform,
            "author": self.author,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "word_count": self.word_count,
            "is_processed": self.is_processed,
            "processing_status": self.processing_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

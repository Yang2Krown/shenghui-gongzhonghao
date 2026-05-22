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
    
    def __repr__(self):
        return f"<StyleProfile(id={self.id}, name='{self.name}', user_id={self.user_id})>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
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
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def analyze_articles(self, articles: List):
        """分析文章风格"""
        # 这里应该实现实际的风格分析逻辑
        # 暂时返回模拟数据
        self.style_features = {
            "common_words": ["AI", "人工智能", "技术", "发展", "应用"],
            "sentence_patterns": ["主谓宾结构", "并列句", "复合句"],
            "tone_indicators": ["专业术语", "数据引用", "案例分析"],
            "structure_patterns": ["总分总", "问题-解决方案", "时间顺序"]
        }
        self.confidence_score = 0.85
        self.updated_at = datetime.utcnow()


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
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
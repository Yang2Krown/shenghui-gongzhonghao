from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import BaseModel


class ContentCreation(BaseModel):
    """内容创作模型"""
    __tablename__ = "content_creations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)
    status = Column(String(20), default="draft")  # draft, published, archived
    style_profile_id = Column(Integer, ForeignKey("style_profiles.id"), nullable=True)
    
    # 内容元数据
    word_count = Column(Integer, default=0)
    reading_time = Column(Integer, default=0)  # 预计阅读时间（分钟）
    featured_image = Column(String(1000), nullable=True)
    tags = Column(JSON, default=[])
    summary = Column(Text, nullable=True)
    
    # 发布信息
    published_at = Column(DateTime, nullable=True)
    published_platform = Column(String(50), nullable=True)
    platform_url = Column(String(1000), nullable=True)
    
    # 统计数据
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关系
    user = relationship("User", back_populates="creations")
    topic = relationship("Topic", back_populates="creations")
    style_profile = relationship("StyleProfile", back_populates="creations")
    
    def __repr__(self):
        return f"<ContentCreation(id={self.id}, title='{self.title[:50]}...', status='{self.status}')>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "topic_id": self.topic_id,
            "title": self.title,
            "content": self.content,
            "status": self.status,
            "style_profile_id": self.style_profile_id,
            "word_count": self.word_count,
            "reading_time": self.reading_time,
            "featured_image": self.featured_image,
            "tags": self.tags,
            "summary": self.summary,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "published_platform": self.published_platform,
            "platform_url": self.platform_url,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "share_count": self.share_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def update_content(self, content: str):
        """更新内容"""
        self.content = content
        self.word_count = len(content)
        self.reading_time = max(1, len(content) // 500)  # 假设每分钟500字
        self.updated_at = datetime.utcnow()
    
    def publish(self, platform: str = None, url: str = None):
        """发布创作"""
        self.status = "published"
        self.published_at = datetime.utcnow()
        if platform:
            self.published_platform = platform
        if url:
            self.platform_url = url
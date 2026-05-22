from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import BaseModel


class Topic(BaseModel):
    """选题模型"""
    __tablename__ = "topics"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    content_summary = Column(Text, nullable=True)
    source_platform = Column(String(50), nullable=False)  # 36kr, qbitai, jiqizhixin, etc.
    source_url = Column(String(1000), nullable=False)
    category = Column(String(100), nullable=True)  # AI, 机器学习, 自然语言处理, etc.
    heat_score = Column(Integer, default=0)  # 热度分数
    published_at = Column(DateTime, nullable=True)
    scraped_at = Column(DateTime, default=func.now(), nullable=False)
    is_processed = Column(Boolean, default=False)
    keywords = Column(JSON, default=[])  # 关键词列表
    image_url = Column(String(1000), nullable=True)
    author = Column(String(200), nullable=True)
    read_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关系
    collections = relationship("TopicCollection", back_populates="topic", cascade="all, delete-orphan")
    creations = relationship("ContentCreation", back_populates="topic")
    
    def __repr__(self):
        return f"<Topic(id={self.id}, title='{self.title[:50]}...', platform='{self.source_platform}')>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "content_summary": self.content_summary,
            "source_platform": self.source_platform,
            "source_url": self.source_url,
            "category": self.category,
            "heat_score": self.heat_score,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "is_processed": self.is_processed,
            "keywords": self.keywords,
            "image_url": self.image_url,
            "author": self.author,
            "read_count": self.read_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class TopicCollection(BaseModel):
    """选题收藏模型"""
    __tablename__ = "topic_collections"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    collected_at = Column(DateTime, default=func.now(), nullable=False)
    notes = Column(Text, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关系
    user = relationship("User", back_populates="collections")
    topic = relationship("Topic", back_populates="collections")
    
    def __repr__(self):
        return f"<TopicCollection(id={self.id}, user_id={self.user_id}, topic_id={self.topic_id})>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "topic_id": self.topic_id,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
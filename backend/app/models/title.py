"""
标题生成结果数据模型

定义标题生成结果的数据结构，包括候选标题、评分和最终推荐。
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, DateTime, Integer, Float, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class TitleCandidate(Base):
    """
    候选标题模型
    
    存储Agent A生成的候选标题信息。
    """
    
    __tablename__ = "title_candidates"
    
    # 主键
    id = Column(String(36), primary_key=True, index=True, comment="候选ID")
    result_id = Column(
        String(36),
        ForeignKey("title_generation_results.id"),
        nullable=False,
        comment="结果ID",
    )
    
    # 候选信息
    sequence = Column(Integer, nullable=False, comment="序号")
    title = Column(String(255), nullable=False, comment="标题内容")
    word_count = Column(Integer, nullable=False, comment="字数")
    method = Column(String(50), nullable=False, comment="套路名称")
    modifiers = Column(JSON, nullable=True, comment="修饰元素列表")
    explanation = Column(Text, nullable=True, comment="简短说明")
    
    # 评分信息 (Agent B)
    b_score = Column(Float, nullable=True, comment="Agent B评分总分")
    b_score_details = Column(JSON, nullable=True, comment="Agent B评分详情")
    
    # 点击预测 (Agent C)
    c_click_willingness = Column(Float, nullable=True, comment="点击意愿(0-10)")
    c_click_reason = Column(Text, nullable=True, comment="会点原因")
    c_no_click_reason = Column(Text, nullable=True, comment="不点原因")
    c_improvement_suggestion = Column(Text, nullable=True, comment="改进建议")
    
    # 综合评分
    final_score = Column(Float, nullable=True, comment="最终综合评分")
    
    # 状态
    is_eliminated = Column(
        String(1),
        default="0",
        nullable=False,
        comment="是否被一票否决",
    )
    elimination_reason = Column(Text, nullable=True, comment="淘汰原因")
    is_top5 = Column(
        String(1),
        default="0",
        nullable=False,
        comment="是否进入Top 5",
    )
    is_top3 = Column(
        String(1),
        default="0",
        nullable=False,
        comment="是否进入Top 3",
    )
    
    # 时间戳
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    
    # 关系
    result = relationship("TitleGenerationResult", back_populates="candidates")
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"<TitleCandidate(id={self.id}, title={self.title})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "sequence": self.sequence,
            "title": self.title,
            "word_count": self.word_count,
            "method": self.method,
            "modifiers": self.modifiers,
            "explanation": self.explanation,
            "b_score": self.b_score,
            "b_score_details": self.b_score_details,
            "c_click_willingness": self.c_click_willingness,
            "c_click_reason": self.c_click_reason,
            "c_no_click_reason": self.c_no_click_reason,
            "c_improvement_suggestion": self.c_improvement_suggestion,
            "final_score": self.final_score,
            "is_eliminated": self.is_eliminated,
            "elimination_reason": self.elimination_reason,
            "is_top5": self.is_top5,
            "is_top3": self.is_top3,
        }


class FinalRecommendation(Base):
    """
    最终推荐标题模型
    
    存储Agent D输出的Top 3推荐标题。
    """
    
    __tablename__ = "final_recommendations"
    
    # 主键
    id = Column(String(36), primary_key=True, index=True, comment="推荐ID")
    result_id = Column(
        String(36),
        ForeignKey("title_generation_results.id"),
        nullable=False,
        comment="结果ID",
    )
    
    # 推荐信息
    rank = Column(Integer, nullable=False, comment="排名(1-3)")
    title = Column(String(255), nullable=False, comment="标题内容")
    word_count = Column(Integer, nullable=False, comment="字数")
    method = Column(String(50), nullable=False, comment="套路名称")
    modifiers = Column(JSON, nullable=True, comment="修饰元素列表")
    
    # 评分信息
    b_score = Column(Float, nullable=False, comment="Agent B评分总分")
    c_click_willingness = Column(Float, nullable=False, comment="点击意愿(0-10)")
    final_score = Column(Float, nullable=False, comment="最终综合评分")
    recommendation_reason = Column(Text, nullable=True, comment="推荐理由")
    
    # 时间戳
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    
    # 关系
    result = relationship("TitleGenerationResult", back_populates="recommendations")
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"<FinalRecommendation(id={self.id}, rank={self.rank}, title={self.title})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "rank": self.rank,
            "title": self.title,
            "word_count": self.word_count,
            "method": self.method,
            "modifiers": self.modifiers,
            "b_score": self.b_score,
            "c_click_willingness": self.c_click_willingness,
            "final_score": self.final_score,
            "recommendation_reason": self.recommendation_reason,
        }


class TitleGenerationResult(Base):
    """
    标题生成结果模型
    
    存储整个标题生成过程的结果和归档信息。
    """
    
    __tablename__ = "title_generation_results"
    
    # 主键
    id = Column(String(36), primary_key=True, index=True, comment="结果ID")
    task_id = Column(
        String(36),
        ForeignKey("tasks.id"),
        nullable=False,
        unique=True,
        comment="任务ID",
    )
    
    # 生成过程统计
    total_candidates = Column(Integer, nullable=True, comment="候选总数")
    covered_methods = Column(Integer, nullable=True, comment="覆盖套路数")
    eliminated_count = Column(Integer, nullable=True, comment="一票否决淘汰数")
    regeneration_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="重生次数",
    )
    
    # 自检结果
    self_check_passed = Column(
        String(1),
        default="0",
        nullable=False,
        comment="自检是否通过",
    )
    self_check_details = Column(JSON, nullable=True, comment="自检详情")
    
    # 异常信息
    exceptions = Column(JSON, nullable=True, comment="异常信息列表")
    
    # 时间戳
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="完成时间",
    )
    duration_seconds = Column(Float, nullable=True, comment="耗时(秒)")
    
    # 关系
    candidates = relationship(
        "TitleCandidate",
        back_populates="result",
        cascade="all, delete-orphan",
    )
    recommendations = relationship(
        "FinalRecommendation",
        back_populates="result",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"<TitleGenerationResult(id={self.id}, task_id={self.task_id})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "total_candidates": self.total_candidates,
            "covered_methods": self.covered_methods,
            "eliminated_count": self.eliminated_count,
            "regeneration_count": self.regeneration_count,
            "self_check_passed": self.self_check_passed,
            "self_check_details": self.self_check_details,
            "exceptions": self.exceptions,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "candidates": [c.to_dict() for c in self.candidates] if self.candidates else [],
            "recommendations": [r.to_dict() for r in self.recommendations] if self.recommendations else [],
        }

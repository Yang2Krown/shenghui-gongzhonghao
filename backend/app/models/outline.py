"""大纲生成模块的数据模型。

对齐《大纲生成 Agent 设计文档》6.2 节的最终大纲格式。
"""

from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.db.base import BaseModel, JSONField


class Outline(BaseModel):
    """大纲主表。"""
    __tablename__ = "outlines"

    # 关联选题候选
    candidate_id = Column(Integer, ForeignKey("topic_candidates.id"), nullable=False, index=True)
    
    # 大纲元信息
    title = Column(String(500), nullable=False)  # 大纲标题（来自选题）
    direction = Column(String(50), nullable=True)  # 内容方向
    routine = Column(String(200), nullable=True)  # 套路
    
    # 大纲内容
    sections = Column(JSONField, default=list)  # 节列表（中粒度大纲）
    total_words = Column(Integer, default=0)  # 总字数估算
    section_count = Column(Integer, default=0)  # 节数
    
    # 生成过程
    generation_process = Column(JSONField, default=dict)  # 生成过程记录
    
    # 自检评分
    inspection_score = Column(JSONField, default=dict)  # 自检评分明细
    total_score = Column(Float, default=0.0)  # 总分
    passed = Column(String(20), default="pending")  # pending / passed / failed
    
    # 关联关系
    candidate = relationship("TopicCandidate", back_populates="outlines")
    candidates = relationship("OutlineCandidate", back_populates="outline", cascade="all, delete-orphan")
    review = relationship("OutlineReview", back_populates="outline", uselist=False, cascade="all, delete-orphan")
    criticism = relationship("OutlineCriticism", back_populates="outline", uselist=False, cascade="all, delete-orphan")
    inspection = relationship("OutlineInspection", back_populates="outline", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_outline_candidate", "candidate_id"),
        Index("ix_outline_passed", "passed"),
    )
    
    def __repr__(self):
        return f"<Outline(id={self.id}, title='{self.title[:30]}...', passed='{self.passed}')>"


class OutlineCandidate(BaseModel):
    """大纲候选表（Agent A 输出的 3 个候选）。"""
    __tablename__ = "outline_candidates"
    
    outline_id = Column(Integer, ForeignKey("outlines.id"), nullable=False, index=True)
    candidate_number = Column(Integer, nullable=False)  # 候选编号 1/2/3
    
    # 候选内容
    hook_type = Column(String(50), nullable=False)  # 开头钩子类型
    skeleton_feature = Column(Text, nullable=True)  # 骨架特点描述
    sections = Column(JSONField, default=list)  # 节列表
    total_words = Column(Integer, default=0)  # 总字数估算
    
    # 关联关系
    outline = relationship("Outline", back_populates="candidates")
    
    __table_args__ = (
        Index("ix_outline_candidate_outline", "outline_id"),
    )
    
    def __repr__(self):
        return f"<OutlineCandidate(id={self.id}, outline_id={self.outline_id}, number={self.candidate_number})>"


class OutlineReview(BaseModel):
    """大纲评审记录（Agent B 输出）。"""
    __tablename__ = "outline_reviews"
    
    outline_id = Column(Integer, ForeignKey("outlines.id"), nullable=False, unique=True, index=True)
    
    # 评审结果
    selected_candidate = Column(Integer, nullable=True)  # 选中的候选编号
    review_reason = Column(Text, nullable=True)  # 评审理由
    
    # 评审后大纲（含传播标签）
    reviewed_sections = Column(JSONField, default=list)  # 评审后节列表
    
    # 关联关系
    outline = relationship("Outline", back_populates="review")
    
    def __repr__(self):
        return f"<OutlineReview(id={self.id}, outline_id={self.outline_id})>"


class OutlineCriticism(BaseModel):
    """读者挑刺记录（Agent C 输出）。"""
    __tablename__ = "outline_criticisms"
    
    outline_id = Column(Integer, ForeignKey("outlines.id"), nullable=False, unique=True, index=True)
    
    # 挑刺结果
    overall_feeling = Column(Text, nullable=True)  # 整体感受
    problem_sections = Column(JSONField, default=list)  # 问题节列表
    
    # 修订后大纲
    revised_sections = Column(JSONField, default=list)  # 修订后节列表
    
    # 关联关系
    outline = relationship("Outline", back_populates="criticism")
    
    def __repr__(self):
        return f"<OutlineCriticism(id={self.id}, outline_id={self.outline_id})>"


class OutlineInspection(BaseModel):
    """大纲自检记录（Agent D 输出）。"""
    __tablename__ = "outline_inspections"
    
    outline_id = Column(Integer, ForeignKey("outlines.id"), nullable=False, unique=True, index=True)
    
    # 自检评分明细
    hook_score = Column(Float, default=0.0)  # 开头钩子强度 (20%)
    value_ladder_score = Column(Float, default=0.0)  # 价值阶梯递进 (20%)
    rhythm_score = Column(Float, default=0.0)  # 节奏感 (15%)
    title_scan_score = Column(Float, default=0.0)  # 小标题扫读友好度 (15%)
    trigger_score = Column(Float, default=0.0)  # 传播触发点完整度 (20%)
    length_score = Column(Float, default=0.0)  # 长度与节数匹配 (10%)
    
    total_score = Column(Float, default=0.0)  # 总分
    verdict = Column(String(20), default="pending")  # pending / passed / failed
    
    # 扣分理由（仅在不通过时）
    deduction_reasons = Column(JSONField, default=list)
    
    # 关联关系
    outline = relationship("Outline", back_populates="inspection")
    
    def __repr__(self):
        return f"<OutlineInspection(id={self.id}, outline_id={self.outline_id}, score={self.total_score})>"

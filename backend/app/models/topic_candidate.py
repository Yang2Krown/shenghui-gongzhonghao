"""候选选题表：Agent A 衍生 + Agent B 评分的产物。

对齐《选题挖掘 Agent 设计文档》2.5 / 3.4 节输出格式。
PersonaReview 4 行（每 candidate 4 个 Persona） + CandidateScore 1 行（6 维度评分）。
"""

from sqlalchemy import Column, Integer, String, Text, Float, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import BaseModel, JSONField


# Persona 名（设计文档 2.3 节）
PERSONA_AI_EXPERT = "AI专家"
PERSONA_VIRAL_BLOGGER = "百万粉博主"
PERSONA_PM = "产品经理"
PERSONA_OPS = "运营专家"

# Agent B 判定（设计文档 3.3 节）
VERDICT_SELECTED = "selected"        # ≥ 7.0 入选
VERDICT_BACKUP = "backup"            # 5.0 - 7.0 备选
VERDICT_REJECTED = "rejected"        # < 5.0 淘汰
VERDICT_VETOED = "vetoed"            # 一票否决


class TopicCandidate(BaseModel):
    """候选选题主表（Agent A 输出 + Agent B 评分快照）。"""
    __tablename__ = "topic_candidates"

    info_cluster_id = Column(Integer, ForeignKey("info_clusters.id"), nullable=True, index=True)

    # Agent A：衍生信息
    title = Column(String(500), nullable=False)                        # 草标题 14-22 字
    direction = Column(String(50), nullable=True, index=True)          # 6 大内容方向之一
    routine = Column(String(200), nullable=True)                       # 套路（如 "1.1.1 深度解读型"）
    dimension_combo = Column(JSONField, default=list)                       # 8 维度组合（["态度=吹爆", "结构=列表"]）
    value_promise = Column(Text, nullable=True)                        # 价值承诺
    angle_note = Column(Text, nullable=True)                           # 切入说明

    # Persona 分歧度（max - min）
    persona_divergence = Column(Float, default=0.0)                    # ≥ 4 触发 ⚠️ 标注
    persona_divergence_flag = Column(Boolean, default=False, index=True)

    # Agent B：评分汇总
    veto_passed = Column(Boolean, default=True, index=True)            # 一票否决是否通过
    veto_reasons = Column(JSONField, default=list)                          # ["纯标题党", ...]
    # 商务敏感：设计文档 3.3 节"严厉唱衰国内厂商 → 标记不直接淘汰"
    business_sensitive = Column(Boolean, default=False, index=True)    # 需人工复核
    weighted_score = Column(Float, nullable=True, index=True)          # 加权总分 0-10
    verdict = Column(String(20), nullable=True, index=True)            # 见 VERDICT_*

    info_cluster = relationship("InfoCluster", back_populates="candidates")
    persona_reviews = relationship("PersonaReview", back_populates="candidate", cascade="all, delete-orphan")
    score = relationship("CandidateScore", back_populates="candidate", uselist=False, cascade="all, delete-orphan")
    outlines = relationship("Outline", back_populates="candidate", cascade="all, delete-orphan")

    __table_args__ = (
        # 下游全局排序主查询：拉 verdict='selected' 按 weighted_score 排序
        Index("ix_candidate_verdict_score", "verdict", "weighted_score"),
        Index("ix_candidate_direction_score", "direction", "weighted_score"),
    )

    def __repr__(self):
        return f"<TopicCandidate(id={self.id}, title='{(self.title or '')[:30]}...', verdict='{self.verdict}')>"


class PersonaReview(BaseModel):
    """4 Persona 评议（每个候选 4 行）。"""
    __tablename__ = "persona_reviews"

    candidate_id = Column(Integer, ForeignKey("topic_candidates.id"), nullable=False, index=True)
    persona = Column(String(30), nullable=False)                       # 见 PERSONA_*
    score = Column(Float, nullable=False)                              # 0-10
    rationale = Column(Text, nullable=True)                            # 1 句话理由

    candidate = relationship("TopicCandidate", back_populates="persona_reviews")

    def __repr__(self):
        return f"<PersonaReview(candidate={self.candidate_id}, persona='{self.persona}', score={self.score})>"


class CandidateScore(BaseModel):
    """6 维度评分（每个候选 1 行）。维度对齐设计文档 3.3 节。"""
    __tablename__ = "candidate_scores"

    candidate_id = Column(Integer, ForeignKey("topic_candidates.id"), nullable=False, unique=True, index=True)

    # 6 维度分数（0-10）
    pain_point = Column(Float, nullable=False)                         # 痛点直击度 20%
    value_density = Column(Float, nullable=False)                      # 价值密度 20%
    propagation = Column(Float, nullable=False)                        # 传播触发器 15%
    differentiation = Column(Float, nullable=False)                    # 差异化 15%
    freshness = Column(Float, nullable=False)                          # 新鲜度 10%
    audience_fit = Column(Float, nullable=False)                       # 受众适配度 20%

    # 每个维度的"依据"（设计文档要求必须附 1 句话依据）
    evidence = Column(JSONField, default=dict)                              # {pain_point: "...", value_density: "...", ...}

    candidate = relationship("TopicCandidate", back_populates="score")

    def __repr__(self):
        return f"<CandidateScore(candidate={self.candidate_id})>"

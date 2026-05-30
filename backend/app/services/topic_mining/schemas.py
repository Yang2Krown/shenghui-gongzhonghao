"""选题挖掘 Agent 的 I/O 契约（Pydantic schemas）。

对齐设计文档 1.4 / 2.5 / 3.4 节的输入输出格式。
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Agent A 输入
# ──────────────────────────────────────────────

class InfoClusterInput(BaseModel):
    """预处理后的信息（Agent A 的输入）。对齐设计文档 1.4 节。"""
    cluster_id: int
    core_title: str
    summary: Optional[str] = None
    info_type: str = Field(description="资讯型 / 实操案例型 / 观点分享型 / 教程型")
    direction: Optional[str] = None
    elements: dict = Field(default_factory=dict, description="{主体, 动作, 对象, 亮点, 争议, 数据}")
    freshness: Optional[str] = Field(default=None, description="24h / 7d / 30d / expired")
    heat_score: float = 0.0
    low_fan_hit: bool = False
    source_urls: List[str] = Field(default_factory=list)


# ──────────────────────────────────────────────
# Agent A 输出
# ──────────────────────────────────────────────

class PersonaReviewItem(BaseModel):
    """单个 Persona 的评议。"""
    persona: str = Field(description="AI专家 / 百万粉博主 / 产品经理 / 运营专家")
    score: float = Field(ge=0, le=10)
    rationale: str

    class Config:
        # 兼容 LLM 返回 role/reason 等变体字段名
        populate_by_name = True

    @classmethod
    def from_llm_output(cls, data: dict) -> "PersonaReviewItem":
        """从 LLM 输出构建，兼容 role/reason 等变体。"""
        return cls(
            persona=data.get("persona") or data.get("role") or data.get("name", ""),
            score=data.get("score", 0),
            rationale=data.get("rationale") or data.get("reason") or data.get("explanation", ""),
        )


class CandidateFromA(BaseModel):
    """Agent A 衍生的单个候选选题。对齐设计文档 2.5 节。"""
    candidate_id: str = Field(description="递增编号，如 T-001")
    title: str = Field(min_length=10, max_length=40, description="草标题，建议 14-22 字，允许放宽到 40 字")
    summary: str = Field(description="选题简介，1-2 句话描述这个选题要写什么、给谁看、为什么值得写")
    direction: str = Field(description="6 大内容方向之一")
    routine: str = Field(description="套路名，如 1.1.1 深度解读型")
    dimension_combo: List[str] = Field(default_factory=list, description='维度组合，如 ["态度=吹爆", "结构=列表"]')
    value_promise: str = Field(description="价值承诺，1 句话")
    angle_note: str = Field(description="切入说明，1-2 句话")
    persona_reviews: List[PersonaReviewItem] = Field(min_length=4, max_length=4)
    persona_divergence: float = Field(description="max - min")
    persona_divergence_flag: bool = Field(default=False, description="max-min >= 4 时为 True")


class AgentAOutput(BaseModel):
    """Agent A 的完整输出。"""
    candidates: List[CandidateFromA]


# ──────────────────────────────────────────────
# Agent B 输入
# ──────────────────────────────────────────────

class AgentBInput(BaseModel):
    """Agent B 的输入：Agent A 的候选列表 + 原始信息摘要。"""
    cluster_id: int
    core_title: str
    info_type: str
    freshness: Optional[str] = None
    candidates: List[CandidateFromA]


# ──────────────────────────────────────────────
# Agent B 输出
# ──────────────────────────────────────────────

class DimensionScore(BaseModel):
    """单维度评分。"""
    score: float = Field(ge=0, le=10)
    evidence: str = Field(description="1 句话评分依据")


class CandidateScored(BaseModel):
    """Agent B 评分后的候选选题。对齐设计文档 3.4 节。"""
    candidate_id: str
    title: str
    summary: Optional[str] = ""
    direction: str
    routine: str
    dimension_combo: List[str] = Field(default_factory=list)
    value_promise: str
    angle_note: Optional[str] = ""

    # 一票否决
    veto_passed: bool
    veto_reasons: List[str] = Field(default_factory=list)
    business_sensitive: bool = Field(default=False, description="商务敏感，需人工复核（不直接淘汰）")

    # 6 维度评分
    pain_point: DimensionScore
    value_density: DimensionScore
    propagation: DimensionScore
    differentiation: DimensionScore
    freshness: DimensionScore
    audience_fit: DimensionScore

    # 汇总
    weighted_score: float
    verdict: str = Field(description="selected / backup / rejected / vetoed")

    # 保留 Agent A 的 Persona 评议
    persona_reviews: List[PersonaReviewItem]
    persona_divergence: float = 0.0
    persona_divergence_flag: bool = False


class AgentBOutput(BaseModel):
    """Agent B 的完整输出。"""
    candidates: List[CandidateScored]
    stats: dict = Field(default_factory=dict, description="{total, selected, backup, rejected, vetoed}")

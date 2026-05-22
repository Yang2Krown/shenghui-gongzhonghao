"""大纲生成 Agent 的 I/O 契约（Pydantic schemas）。

对齐《大纲生成 Agent 设计文档》6.1 / 6.2 节的输入输出格式。
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# 大纲生成输入
# ──────────────────────────────────────────────

class OutlineInput(BaseModel):
    """大纲生成的输入（来自选题候选）。"""
    candidate_id: int
    title: str
    direction: str
    routine: Optional[str] = None
    value_promise: Optional[str] = None
    angle_note: Optional[str] = None
    info_cluster_id: Optional[int] = None
    core_title: Optional[str] = None
    summary: Optional[str] = None


# ──────────────────────────────────────────────
# Agent A 输出（大纲创作员）
# ──────────────────────────────────────────────

class Section(BaseModel):
    """大纲中的单节。"""
    section_number: int = Field(description="节号 1/2/3/...")
    title: str = Field(description="小标题")
    core_points: List[str] = Field(default_factory=list, description="核心信息点")
    word_count: int = Field(default=0, description="字数预估")
    notes: Optional[str] = Field(default=None, description="备注")


class OutlineCandidateItem(BaseModel):
    """单个大纲候选。"""
    candidate_number: int = Field(description="候选编号 1/2/3")
    hook_type: str = Field(description="开头钩子类型")
    skeleton_feature: str = Field(description="骨架特点描述")
    sections: List[Section]
    total_words: int = Field(description="总字数估算")


class AgentAOutput(BaseModel):
    """Agent A 的完整输出（3 个候选大纲）。"""
    candidates: List[OutlineCandidateItem]


# ──────────────────────────────────────────────
# Agent B 输入/输出（大纲评审员）
# ──────────────────────────────────────────────

class AgentBInput(BaseModel):
    """Agent B 的输入。"""
    outline_id: int
    title: str
    direction: str
    candidates: List[OutlineCandidateItem]


class SectionWithTags(BaseModel):
    """带传播标签的节。"""
    section_number: int
    title: str
    core_points: List[str]
    word_count: int
    propagation_tags: List[str] = Field(default_factory=list, description="传播角色标签")
    notes: Optional[str] = None


class AgentBOutput(BaseModel):
    """Agent B 的输出（评审后大纲）。"""
    selected_candidate: int = Field(description="选中的候选编号")
    review_reason: str = Field(description="评审理由")
    sections: List[SectionWithTags]


# ──────────────────────────────────────────────
# Agent C 输入/输出（读者挑刺员）
# ──────────────────────────────────────────────

class AgentCInput(BaseModel):
    """Agent C 的输入。"""
    outline_id: int
    title: str
    sections: List[SectionWithTags]


class ProblemSection(BaseModel):
    """问题节。"""
    section_number: int
    problem_type: str = Field(description="问题类型")
    feedback: str = Field(description="具体反馈")
    suggestion: str = Field(description="修改建议")


class AgentCOutput(BaseModel):
    """Agent C 的输出（挑刺反馈 + 修订后大纲）。"""
    overall_feeling: str = Field(description="整体感受")
    problem_sections: List[ProblemSection]
    revised_sections: List[SectionWithTags]


# ──────────────────────────────────────────────
# Agent D 输入/输出（大纲自检员）
# ──────────────────────────────────────────────

class AgentDInput(BaseModel):
    """Agent D 的输入。"""
    outline_id: int
    title: str
    sections: List[SectionWithTags]


class DimensionScore(BaseModel):
    """单维度评分。"""
    score: float = Field(ge=0, le=10)
    evidence: str = Field(description="评分依据")


class DeductionReason(BaseModel):
    """扣分理由。"""
    dimension: str
    score_lost: float
    reason: str
    suggestion: str


class AgentDOutput(BaseModel):
    """Agent D 的输出（自检评分）。"""
    hook_score: DimensionScore  # 开头钩子强度 (20%)
    value_ladder_score: DimensionScore  # 价值阶梯递进 (20%)
    rhythm_score: DimensionScore  # 节奏感 (15%)
    title_scan_score: DimensionScore  # 小标题扫读友好度 (15%)
    trigger_score: DimensionScore  # 传播触发点完整度 (20%)
    length_score: DimensionScore  # 长度与节数匹配 (10%)
    
    total_score: float
    verdict: str = Field(description="passed / failed")
    deduction_reasons: List[DeductionReason] = Field(default_factory=list)


# ──────────────────────────────────────────────
# 最终大纲输出
# ──────────────────────────────────────────────

class FinalOutline(BaseModel):
    """最终大纲输出（对齐设计文档 6.2 节）。"""
    outline_id: int
    title: str
    direction: str
    routine: Optional[str] = None
    value_promise: Optional[str] = None
    
    sections: List[SectionWithTags]
    total_words: int
    section_count: int
    
    generation_process: dict = Field(default_factory=dict)
    inspection_score: dict = Field(default_factory=dict)
    total_score: float
    passed: str

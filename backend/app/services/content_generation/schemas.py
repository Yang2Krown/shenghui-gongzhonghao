"""正文生成 Agent 的 I/O 契约（Pydantic schemas）。

对齐《正文生成 Agent 设计文档 v1.1》的输入输出格式。
4 Agent 协作：A（正文创作）→ B（金句催化）→ C（去AI味）→ D（整合自检）
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# 总体输入（用户触发正文生成时传入）
# ──────────────────────────────────────────────

class StyleParams(BaseModel):
    """风格参数（用户外部注入，可选）。"""
    tone: Optional[str] = Field(default=None, description="语气描述，如'第一人称、带点自嘲、信息密集'")
    banned_words: List[str] = Field(default_factory=list, description="禁用词清单（硬约束）")
    preferred_words: List[str] = Field(default_factory=list, description="偏好用词清单（软约束）")
    sample_articles: List[str] = Field(default_factory=list, description="历史爆款样本（few-shot 范本）")


class SectionBrief(BaseModel):
    """大纲中的单节简述。"""
    section_number: int = Field(description="节号，从 1 开始")
    subtitle: str = Field(description="小标题")
    core_points: List[str] = Field(default_factory=list, description="核心信息点")
    spread_role: Optional[str] = Field(default=None, description="传播角色：钩子/铺垫/高潮/升华/收尾")
    word_estimate: int = Field(default=500, description="字数预估")
    notes: Optional[str] = Field(default=None, description="备注")


class ContentGenerationInput(BaseModel):
    """正文生成的总输入。对齐设计文档 6.1 节。"""
    # 选题信息
    topic_title: str = Field(description="最终选定标题")
    topic_direction: Optional[str] = Field(default=None, description="内容方向")
    topic_routine: Optional[str] = Field(default=None, description="套路")
    value_promise: Optional[str] = Field(default=None, description="价值承诺")

    # 大纲（已通过自检）
    outline_id: Optional[int] = Field(default=None, description="大纲ID，用于关联")
    sections: List[SectionBrief] = Field(min_length=1, description="大纲各节")

    # 风格参数（可选）
    style_params: Optional[StyleParams] = Field(default=None, description="风格参数")

    # 关联
    candidate_id: Optional[int] = Field(default=None, description="选题候选ID")
    user_id: Optional[int] = Field(default=None, description="用户ID")


# ──────────────────────────────────────────────
# Agent A 输出：正文骨干
# ──────────────────────────────────────────────

class GoldSentenceSeed(BaseModel):
    """Agent A 埋下的金句种子。"""
    section_number: int = Field(description="所在节号")
    position: str = Field(description="位置描述，如'第1节末尾'")
    seed_text: str = Field(description="准金句文本")


class SectionContent(BaseModel):
    """单节正文内容。"""
    section_number: int
    subtitle: str
    content: str = Field(description="该节正文内容")
    word_count: int = Field(description="该节字数")
    gold_seed: Optional[GoldSentenceSeed] = Field(default=None, description="该节的金句种子（如有）")


class AgentAOutput(BaseModel):
    """Agent A（正文创作员）的完整输出。对齐设计文档 2.5 节。"""
    style_anchor: str = Field(description="风格锚点：一句话定义本文语气")
    full_text: str = Field(description="完整正文（不含风格锚点行）")
    total_word_count: int = Field(description="总字数")
    section_count: int = Field(description="节数")
    sections: List[SectionContent] = Field(description="各节内容明细")
    gold_seeds: List[GoldSentenceSeed] = Field(default_factory=list, description="所有金句种子汇总")


# ──────────────────────────────────────────────
# Agent B 输出：金句清单
# ──────────────────────────────────────────────

class GoldSentence(BaseModel):
    """单个金句。对齐设计文档 3.5 节。"""
    sentence_id: int = Field(description="金句编号，从 1 开始")
    sentence_type: str = Field(description="类型：开头钩子金句/中段共鸣金句/反差金句/结尾升华金句/强观点金句/自嘲金句")
    location: str = Field(description="位置描述，如'第1节末尾'")
    section_number: int = Field(description="所在节号")
    insert_method: str = Field(description="插入方式：替换种子/新增")
    content: str = Field(description="金句内容")
    word_count: int = Field(description="金句字数")
    immutable: bool = Field(default=True, description="不可改标签")


class AgentBOutput(BaseModel):
    """Agent B（金句催化员）的完整输出。对齐设计文档 3.5 节。"""
    sentences: List[GoldSentence] = Field(min_length=3, max_length=5, description="3-5个金句")
    stats: Dict[str, Any] = Field(default_factory=dict, description="统计：总数、类型分布")


# ──────────────────────────────────────────────
# Agent C 输出：去AI味改写
# ──────────────────────────────────────────────

class AITasteIssue(BaseModel):
    """单处AI味问题。"""
    location: str = Field(description="位置：第X节第Y段")
    ai_taste_type: str = Field(description="AI味类型：结构性/词汇性/句式性/情感性/思维性/排版性")
    ai_taste_subtype: str = Field(description="具体子类，如'连接词滥用'")
    priority: str = Field(description="优先级：🚫/⚠️/⚪/🔵")
    original_text: str = Field(description="原文")
    rewritten_text: str = Field(description="改写后")
    reason: str = Field(description="改写理由")


class AgentCOutput(BaseModel):
    """Agent C（去AI味改写员）的完整输出。对齐设计文档 4.4 节。"""
    rewritten_text: str = Field(description="改写后的完整正文")
    rewritten_word_count: int = Field(description="改写后字数")
    original_word_count: int = Field(description="改写前字数")
    word_change_pct: float = Field(description="字数变化百分比")

    rewrite_table: List[AITasteIssue] = Field(default_factory=list, description="改写对照表")
    skipped_sections: List[str] = Field(default_factory=list, description="跳过的金句保护段落")

    stats: Dict[str, Any] = Field(default_factory=dict, description="统计：扫描问题总数、各优先级改写数")

    quality_check: Dict[str, Any] = Field(default_factory=dict, description="质量自检：字数变化、原意保留、新引入AI味")


# ──────────────────────────────────────────────
# Agent D 输出：整合 + 自检诊断
# ──────────────────────────────────────────────

class DimensionScore(BaseModel):
    """单维度评分。"""
    score: float = Field(ge=0, le=10)
    weight: float = Field(description="权重百分比")
    evaluation: str = Field(description="评价")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")


class AgentDOutput(BaseModel):
    """Agent D（整合+自检诊断员）的完整输出。对齐设计文档 5.6 节。"""
    final_text: str = Field(description="最终正文（含金句嵌入）")
    final_word_count: int = Field(description="最终字数")

    # 8维度评分
    title_fulfillment: DimensionScore = Field(description="标题承诺兑现度 (20%)")
    outline_alignment: DimensionScore = Field(description="大纲结构对应度 (15%)")
    word_compliance: DimensionScore = Field(description="字数合规 (10%)")
    style_consistency: DimensionScore = Field(description="风格统一性 (15%)")
    deai_thoroughness: DimensionScore = Field(description="去AI味彻底度 (15%)")
    gold_sentence_completeness: DimensionScore = Field(description="金句完整度 (10%)")
    opening_quality: DimensionScore = Field(description="开头质量 (10%)")
    ending_quality: DimensionScore = Field(description="结尾升华度 (5%)")

    total_score: float = Field(description="加权总分，0-10")

    # 建议
    high_priority: List[str] = Field(default_factory=list, description="高优先级修改")
    medium_priority: List[str] = Field(default_factory=list, description="中优先级修改")
    low_priority: List[str] = Field(default_factory=list, description="低优先级修改")
    recommended_action: str = Field(description="建议处理路径：接受发布/局部手改/整篇重写")

    # 过程归档
    process_archive: Dict[str, Any] = Field(default_factory=dict, description="生成过程归档")


# ──────────────────────────────────────────────
# 总输出
# ──────────────────────────────────────────────

class ContentGenerationOutput(BaseModel):
    """正文生成的总输出。对齐设计文档 6.2 节。"""
    # 最终正文
    final_text: str
    final_word_count: int
    section_count: int
    section_word_counts: List[int] = Field(default_factory=list, description="各节字数")

    # 金句清单
    gold_sentences: List[GoldSentence] = Field(default_factory=list)

    # 去AI味改写对照表
    rewrite_table: List[AITasteIssue] = Field(default_factory=list)

    # 自检诊断报告
    diagnosis: AgentDOutput

    # 过程归档
    agent_a_word_count: int = 0
    agent_b_sentence_count: int = 0
    agent_c_rewrite_count: int = 0
    agent_d_final_word_count: int = 0
    style_anchor: str = ""

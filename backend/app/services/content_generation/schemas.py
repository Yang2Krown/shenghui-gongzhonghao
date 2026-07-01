"""正文生成 Agent 的 I/O 契约（Pydantic schemas）。

5 Agent 协作：A（正文创作）→ B（金句催化）→ D（事实总结）→ E（联网纠错）→ C（去AI味）
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
    part: Optional[str] = Field(default="body", description="所属部分：intro / body / conclusion")
    subtitle: str = Field(description="小标题")
    description: Optional[str] = Field(default=None, description="这一节要写什么的人话说明")
    core_points: List[str] = Field(default_factory=list, description="核心信息点")
    spread_role: Optional[str] = Field(default=None, description="传播角色：钩子/铺垫/高潮/收尾")
    word_estimate: int = Field(default=500, description="该节目标字数")
    notes: Optional[str] = Field(default=None, description="备注")


class ContentGenerationInput(BaseModel):
    """正文生成的总输入。对齐设计文档 6.1 节。"""
    # 选题信息
    topic_title: str = Field(description="最终选定标题")
    topic_direction: Optional[str] = Field(default=None, description="内容方向")
    topic_routine: Optional[str] = Field(default=None, description="套路")
    value_promise: Optional[str] = Field(default=None, description="价值承诺")

    # 事实素材（来自信息簇的正文级摘要，正文写作的事实依据）
    source_summary: Optional[str] = Field(default=None, description="信息簇事实摘要，正文不得偏离其中的事实/数据")

    # 事实素材包（Phase 0 提取，按大纲节组织的关键事实）
    source_materials: Optional[str] = Field(default=None, description="Phase 0 提取的事实素材包文本，正文中的具体事实只能来自此处")

    # 大纲（已通过自检）
    outline_id: Optional[int] = Field(default=None, description="大纲ID，用于关联")
    sections: List[SectionBrief] = Field(min_length=1, description="大纲各节")

    # 风格参数（可选）
    style_params: Optional[StyleParams] = Field(default=None, description="风格参数")

    # 作者人设（来自个人资料，可选）
    persona: Optional[str] = Field(default=None, description="作者身份、经验边界和表达立场，用于避免人设崩塌")

    # 小标题策略：True=大纲 subtitle 仅作方向提示，由写手据内容自拟自然小标题
    # （用于实操/商稿流，避免「引入：」「实操：」「结尾升华」这类结构词当标题）
    free_subtitles: bool = Field(default=False, description="是否让写手自拟自然小标题")

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
    ai_taste_type: str = Field(description="AI味类型：铺垫套话/公式化结构/主语缺失/抽象笼统/距离感/节奏问题/过度解释/金句腔/翻译腔/格式问题")
    ai_taste_subtype: str = Field(description="具体子类，如'开场清嗓''二元反转''虚假主体'")
    priority: str = Field(description="优先级：🚫/⚠️")
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
# Agent D / E 输出（正文生成已不再使用，保留供文案润色 content_polish 复用）
# ──────────────────────────────────────────────

class PotentialFactualError(BaseModel):
    """单条潜在事实性错误。"""
    claim: str = Field(description="原文中的事实性陈述")
    error_type: str = Field(description="错误类型：时间/产品名/版本号/数据/人名/机构/价格/其他")
    section_number: int = Field(description="所在节号")
    reason: str = Field(description="为什么可能出错（如：训练集截止日期、信息过时等）")
    search_query: str = Field(description="建议的联网搜索验证关键词")


class AgentDOutput(BaseModel):
    """Agent D（事实总结员）的完整输出。"""
    summary_text: str = Field(description="对正文 + 金句中事实性内容的总结摘要")
    potential_errors: List[PotentialFactualError] = Field(default_factory=list, description="潜在事实性错误列表")
    total_claims_checked: int = Field(description="检查的事实性陈述总数")
    error_count: int = Field(description="潜在错误数")


class FactualCorrection(BaseModel):
    """单条事实性纠错。"""
    original_claim: str = Field(description="原文中的错误陈述")
    corrected_claim: str = Field(description="纠正后的陈述")
    error_type: str = Field(description="错误类型")
    section_number: int = Field(description="所在节号")
    search_result: str = Field(description="联网搜索找到的依据（简述）")
    confidence: str = Field(description="置信度：高/中/低")


class AgentEOutput(BaseModel):
    """Agent E（Kimi 联网纠错员）的完整输出。"""
    corrected_text: str = Field(description="纠错后的完整正文")
    corrected_word_count: int = Field(description="纠错后字数")
    corrections: List[FactualCorrection] = Field(default_factory=list, description="纠错对照表")
    search_queries_used: List[str] = Field(default_factory=list, description="实际使用的搜索关键词")
    total_corrections: int = Field(description="纠错总数")
    high_confidence_corrections: int = Field(description="高置信度纠错数")
    stats: Dict[str, Any] = Field(default_factory=dict, description="统计信息")


# ──────────────────────────────────────────────
# 总输出
# ──────────────────────────────────────────────

class ContentGenerationOutput(BaseModel):
    """正文生成的总输出。"""
    # 最终正文
    final_text: str
    final_word_count: int
    section_count: int
    section_word_counts: List[int] = Field(default_factory=list, description="各节字数")

    # 金句清单
    gold_sentences: List[GoldSentence] = Field(default_factory=list)

    # 去AI味改写对照表
    rewrite_table: List[AITasteIssue] = Field(default_factory=list)

    # 过程归档
    agent_a_word_count: int = 0
    agent_b_sentence_count: int = 0
    agent_c_rewrite_count: int = 0
    style_anchor: str = ""

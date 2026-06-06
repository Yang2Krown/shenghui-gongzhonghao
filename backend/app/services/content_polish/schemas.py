"""文案润色 I/O 契约（Pydantic schemas）。

复用正文生成的 Agent B/D/E/C 四个 Agent，跳过 Agent A，直接接收用户文本进行润色。
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# 润色输入
# ──────────────────────────────────────────────

class PolishInput(BaseModel):
    """文案润色的总输入。用户只需提供文本和可选标题。"""
    text: str = Field(min_length=10, description="用户提供的原始文案文本")
    title: Optional[str] = Field(default=None, description="文章标题（可选，用于金句催化上下文）")


# ──────────────────────────────────────────────
# 润色输出
# ──────────────────────────────────────────────

class PolishOutput(BaseModel):
    """文案润色的总输出。"""
    # 最终润色文本
    polished_text: str = Field(description="润色后的完整正文")
    polished_word_count: int = Field(description="润色后字数")
    original_word_count: int = Field(description="原始字数")

    # 金句清单（Agent B）
    gold_sentences: List[Dict[str, Any]] = Field(default_factory=list, description="催化出的金句清单")

    # 事实纠错报告（Agent D + E）
    factual_summary: Optional[Dict[str, Any]] = Field(default=None, description="Agent D 事实总结报告")
    factual_corrections: Optional[Dict[str, Any]] = Field(default=None, description="Agent E 联网纠错报告")

    # 去AI味改写报告（Agent C）
    rewrite_table: List[Dict[str, Any]] = Field(default_factory=list, description="去AI味改写对照表")
    skipped_sections: List[str] = Field(default_factory=list, description="跳过的金句保护段落")
    quality_check: Optional[Dict[str, Any]] = Field(default=None, description="质量自检报告")

    # 过程归档
    agent_b_sentence_count: int = 0
    agent_c_rewrite_count: int = 0
    agent_d_error_count: int = 0
    agent_e_correction_count: int = 0
    word_change_pct: float = 0.0

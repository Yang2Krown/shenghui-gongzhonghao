"""
芒格版标题生成和评分的数据模式
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ====== 芒格版标题生成 ======

class MungerGenerationRequest(BaseModel):
    """芒格版标题生成请求"""
    content: str = Field(..., min_length=10, description="文章全文或内容摘要")


class TitleItem(BaseModel):
    """候选标题项"""
    title: str = Field(..., description="标题内容")
    dimension: str = Field("", description="所属维度：信息缺口/社会位置/认知冲突")


class EnhancedTitleItem(BaseModel):
    """增强后的标题项"""
    title: str = Field(..., description="标题内容")
    dimension: str = Field("", description="所属维度")
    enhancement: str = Field("", description="增强项")


class VerdictItem(BaseModel):
    """审判结果项"""
    title: str = Field(..., description="标题内容")
    thumb: str = Field("", description="拇指测试结果")
    redline: str = Field("", description="红线结果")
    word_count: int = Field(0, description="字数")
    final_verdict: str = Field("淘汰", description="最终判定")


class MungerGenerationResponse(BaseModel):
    """芒格版标题生成响应"""
    success: bool = Field(..., description="是否成功")
    positioning: str = Field("", description="定位语")
    all_titles: List[TitleItem] = Field(default_factory=list, description="所有候选标题")
    top5: List[EnhancedTitleItem] = Field(default_factory=list, description="Top 5增强标题")
    verdicts: List[VerdictItem] = Field(default_factory=list, description="审判结果")
    final_pick: str = Field("", description="最终推荐标题")
    loop_count: int = Field(0, description="迭代轮数")
    failure_reasons: List[str] = Field(default_factory=list, description="失败原因")
    duration_seconds: float = Field(0, description="耗时（秒）")
    message: str = Field("", description="补充信息")


# ====== 芒格版标题评分 ======

class ScorerRequest(BaseModel):
    """芒格版标题评分请求"""
    title: str = Field(..., min_length=1, max_length=50, description="标题内容")
    summary: Optional[str] = Field(None, description="文章摘要（可选）")


class DimensionScore(BaseModel):
    """维度评分"""
    score: float = Field(0, description="分数")
    diagnosis: str = Field("", description="诊断")


class RedlineResult(BaseModel):
    """红线审查结果"""
    usable: bool = Field(False, description="是否可用")
    char_count: int = Field(0, description="字数")
    char_ok: bool = Field(False, description="字数是否合规")
    raw_redlines: str = Field("", description="原始红线结果")


class RewriteSuggestion(BaseModel):
    """改写建议"""
    title: str = Field(..., description="改写后的标题")
    fix: str = Field("", description="修复了什么")
    keep: str = Field("", description="保留了什么")


class ScorerResponse(BaseModel):
    """芒格版标题评分响应"""
    success: bool = Field(..., description="是否成功")
    title: str = Field("", description="原始标题")
    analysis: Dict[str, Any] = Field(default_factory=dict, description="结构分析")

    # 三维度评分
    scores: Dict[str, Any] = Field(default_factory=dict, description="各维度评分")

    # 红线审查
    redlines: Dict[str, Any] = Field(default_factory=dict, description="红线审查结果")

    # 总分和等级
    total_score: float = Field(0, description="总分")
    grade: str = Field("", description="等级")
    grade_label: str = Field("", description="等级说明")

    # 诊断和改写
    diagnosis: Any = Field(None, description="综合诊断")
    rewrites: List[RewriteSuggestion] = Field(default_factory=list, description="改写建议")

    # 元信息
    duration_seconds: float = Field(0, description="耗时（秒）")
    error: Optional[str] = Field(None, description="错误信息")

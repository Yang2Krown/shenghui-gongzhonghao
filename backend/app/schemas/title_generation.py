"""
标题生成数据模式

定义标题生成相关的Pydantic数据模式。
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from app.models.task import TaskStatus


class TopicInfo(BaseModel):
    """选题信息模式"""
    title: str = Field(..., min_length=1, max_length=255, description="选题标题(草标题)")
    direction: str = Field(default="", description="内容方向(实践型/解决问题型/教程型/观点型/整活型/资讯型)")
    method: str = Field(default="", description="选题套路")
    value_promise: str = Field(default="", description="价值承诺")

    @validator('direction')
    def validate_direction(cls, v):
        """验证内容方向（支持组合，如"实践型+观点型"）"""
        if not v:
            return v  # 允许为空，从大纲流程过来时可能没有
        valid_directions = {'实践型', '解决问题型', '教程型', '观点型', '整活型', '资讯型'}
        # 支持组合方向（+、/、, 分隔），只要其中每个方向合法即可
        parts = [p.strip() for p in v.replace('/', '+').replace(',', '+').split('+') if p.strip()]
        if not parts:
            raise ValueError(f'内容方向不能为空')
        bad = [p for p in parts if p not in valid_directions]
        if bad:
            raise ValueError(f'内容方向包含无效值: {", ".join(bad)}。允许值: {", ".join(valid_directions)}')
        return v


class OutlineInfo(BaseModel):
    """大纲信息模式"""
    section_titles: List[str] = Field(default_factory=list, description="各节小标题")
    key_points: List[str] = Field(default_factory=list, description="关键信息点")
    spread_tags: List[str] = Field(default_factory=list, description="传播标签分布")


class ContentInfo(BaseModel):
    """正文信息模式（用于标题生成参考）"""
    final_text: str = Field(default="", description="最终正文内容")
    final_word_count: Optional[int] = Field(None, description="正文字数")
    gold_sentences: Optional[List[Any]] = Field(default_factory=list, description="金句列表（字符串或对象均可）")

    @validator("gold_sentences", pre=True)
    def normalize_gold_sentences(cls, v):
        """兼容字符串列表和结构化金句对象列表"""
        if not v:
            return []
        result = []
        for item in v:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                result.append(item.get("content", ""))
            else:
                result.append(str(item))
        return result


class TitleGenerationRequest(BaseModel):
    """标题生成请求模式"""
    topic: TopicInfo = Field(..., description="选题信息")
    outline: OutlineInfo = Field(..., description="大纲信息")
    content: Optional[ContentInfo] = Field(None, description="正文信息（可选，用于标题参考正文）")
    use_primary_model: Optional[bool] = Field(True, description="是否使用主模型")


class TitleGenerationResponse(BaseModel):
    """标题生成响应模式"""
    task_id: str = Field(..., description="任务ID")
    run_id: Optional[str] = Field(None, description="进度流 ID，用于 SSE 连接")
    status: TaskStatus = Field(..., description="任务状态")
    message: str = Field(..., description="响应消息")


class BScoreDetails(BaseModel):
    """Agent B评分详情模式"""
    three_eyes: float = Field(..., ge=0, le=10, description="三个一眼达标度(17%)")
    emotion_trigger: float = Field(..., ge=0, le=10, description="情绪触发力度(18%)")
    infectiousness: Optional[float] = Field(None, ge=0, le=10, description="感染力/传播冲动(16%)")
    afeng_style_fit: Optional[float] = Field(None, ge=0, le=10, description="阿枫科技式真人实测口语感(14%)")
    specificity: float = Field(..., ge=0, le=10, description="具体性(12%)")
    length_compliance: float = Field(..., ge=0, le=10, description="长度合规(4%)")
    method_maturity: float = Field(..., ge=0, le=10, description="套路成熟度(6%)")
    outline_consistency: float = Field(..., ge=0, le=10, description="与大纲一致性(13%)")


class TitleCandidateResponse(BaseModel):
    """候选标题响应模式"""
    id: str = Field(..., description="候选ID")
    sequence: int = Field(..., description="序号")
    title: str = Field(..., description="标题内容")
    word_count: int = Field(..., description="字数")
    method: str = Field(..., description="套路名称")
    modifiers: List[str] = Field(default_factory=list, description="修饰元素列表")
    explanation: Optional[str] = Field(None, description="简短说明")
    
    # Agent B评分
    b_score: Optional[float] = Field(None, ge=0, le=10, description="Agent B评分总分")
    b_score_details: Optional[BScoreDetails] = Field(None, description="Agent B评分详情")
    
    # Agent C点击预测
    c_click_willingness: Optional[float] = Field(None, ge=0, le=10, description="点击意愿(0-10)")
    c_click_reason: Optional[str] = Field(None, description="会点原因")
    c_no_click_reason: Optional[str] = Field(None, description="不点原因")
    c_improvement_suggestion: Optional[str] = Field(None, description="改进建议")
    
    # 综合评分
    final_score: Optional[float] = Field(None, ge=0, le=10, description="最终综合评分")
    
    # 状态
    is_eliminated: bool = Field(False, description="是否被一票否决")
    elimination_reason: Optional[str] = Field(None, description="淘汰原因")
    is_top5: bool = Field(False, description="是否进入Top 5")
    is_top3: bool = Field(False, description="是否进入Top 3")

    class Config:
        """Pydantic配置"""
        from_attributes = True


class FinalRecommendationResponse(BaseModel):
    """最终推荐响应模式"""
    id: str = Field(..., description="推荐ID")
    rank: int = Field(..., ge=1, le=3, description="排名(1-3)")
    title: str = Field(..., description="标题内容")
    word_count: int = Field(..., description="字数")
    method: str = Field(..., description="套路名称")
    modifiers: List[str] = Field(default_factory=list, description="修饰元素列表")
    
    # 评分信息
    b_score: float = Field(..., ge=0, le=10, description="Agent B评分总分")
    c_click_willingness: float = Field(..., ge=0, le=10, description="点击意愿(0-10)")
    final_score: float = Field(..., ge=0, le=10, description="最终综合评分")
    recommendation_reason: Optional[str] = Field(None, description="推荐理由")

    class Config:
        """Pydantic配置"""
        from_attributes = True


class TitleGenerationResultResponse(BaseModel):
    """标题生成结果响应模式"""
    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    message: str = Field(..., description="响应消息")
    result: Optional[Dict[str, Any]] = Field(None, description="生成结果")

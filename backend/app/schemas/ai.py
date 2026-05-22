from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class StyleAnalysisRequest(BaseModel):
    """风格分析请求模型"""
    article_ids: List[int] = Field(..., min_items=1, description="文章ID列表")
    style_profile_id: Optional[int] = Field(None, description="风格档案ID")
    analysis_type: str = Field("comprehensive", description="分析类型：basic, comprehensive, detailed")
    
    @validator("analysis_type")
    def validate_analysis_type(cls, v):
        """验证分析类型"""
        allowed_types = ["basic", "comprehensive", "detailed"]
        if v not in allowed_types:
            raise ValueError(f"分析类型必须是以下之一: {', '.join(allowed_types)}")
        return v


class StyleAnalysisResponse(BaseModel):
    """风格分析响应模型"""
    style_features: Dict[str, Any]
    analysis_summary: str
    confidence_score: float
    recommendations: List[str]


class ContentGenerationRequest(BaseModel):
    """内容生成请求模型"""
    topic_title: str = Field(..., max_length=500, description="选题标题")
    topic_summary: Optional[str] = Field(None, description="选题摘要")
    style_profile_id: Optional[int] = Field(None, description="风格档案ID")
    custom_prompt: Optional[str] = Field(None, max_length=1000, description="自定义提示词")
    content_type: str = Field("article", description="内容类型")
    max_length: Optional[int] = Field(2000, description="最大长度")
    language: str = Field("zh-CN", description="语言")
    
    @validator("content_type")
    def validate_content_type(cls, v):
        """验证内容类型"""
        allowed_types = ["article", "summary", "outline", "social_post", "newsletter"]
        if v not in allowed_types:
            raise ValueError(f"内容类型必须是以下之一: {', '.join(allowed_types)}")
        return v


class ContentGenerationResponse(BaseModel):
    """内容生成响应模型"""
    generated_content: str
    word_count: int
    content_type: str
    style_applied: bool
    suggestions: List[str]


class ContentSummaryRequest(BaseModel):
    """内容摘要请求模型"""
    content: str = Field(..., min_length=100, description="原始内容")
    max_length: Optional[int] = Field(500, description="最大长度")
    summary_style: str = Field("concise", description="摘要风格：concise, detailed, bullet_points")
    include_keywords: bool = Field(True, description="是否包含关键词")
    
    @validator("summary_style")
    def validate_summary_style(cls, v):
        """验证摘要风格"""
        allowed_styles = ["concise", "detailed", "bullet_points", "academic"]
        if v not in allowed_styles:
            raise ValueError(f"摘要风格必须是以下之一: {', '.join(allowed_styles)}")
        return v


class ContentSummaryResponse(BaseModel):
    """内容摘要响应模型"""
    summary: str
    original_length: int
    summary_length: int
    compression_ratio: float
    key_points: List[str]


class TitleSuggestionRequest(BaseModel):
    """标题建议请求模型"""
    content: Optional[str] = Field(None, description="文章内容")
    topic: Optional[str] = Field(None, max_length=200, description="主题")
    count: int = Field(5, ge=1, le=20, description="建议数量")
    title_style: str = Field("engaging", description="标题风格：engaging, professional, clickbait, informative")
    include_numbers: bool = Field(True, description="是否包含数字")
    include_questions: bool = Field(True, description="是否包含问句")
    
    @validator("title_style")
    def validate_title_style(cls, v):
        """验证标题风格"""
        allowed_styles = ["engaging", "professional", "clickbait", "informative", "emotional"]
        if v not in allowed_styles:
            raise ValueError(f"标题风格必须是以下之一: {', '.join(allowed_styles)}")
        return v


class TitleSuggestionResponse(BaseModel):
    """标题建议响应模型"""
    titles: List[str]
    count: int
    style: str
    recommendations: List[str]


class AIModelConfig(BaseModel):
    """AI模型配置"""
    provider: str = Field(..., description="提供商：openai, deepseek, tongyi")
    model_name: str = Field(..., description="模型名称")
    api_key: Optional[str] = Field(None, description="API密钥")
    api_base: Optional[str] = Field(None, description="API基础URL")
    temperature: float = Field(0.7, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(2000, ge=1, le=8000, description="最大token数")
    top_p: float = Field(1.0, ge=0, le=1, description="Top P参数")
    
    @validator("provider")
    def validate_provider(cls, v):
        """验证提供商"""
        allowed_providers = ["openai", "deepseek", "tongyi", "local"]
        if v not in allowed_providers:
            raise ValueError(f"提供商必须是以下之一: {', '.join(allowed_providers)}")
        return v


class AIGenerationOptions(BaseModel):
    """AI生成选项"""
    style_profile: Optional[Dict[str, Any]] = None
    custom_prompt: Optional[str] = None
    content_type: str = "article"
    max_length: int = 2000
    language: str = "zh-CN"
    include_outline: bool = False
    include_examples: bool = True
    include_statistics: bool = True
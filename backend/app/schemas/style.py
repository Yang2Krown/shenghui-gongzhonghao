from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class StyleProfileBase(BaseModel):
    """风格档案基础模型"""
    name: str = Field(..., max_length=100, description="风格名称")
    description: Optional[str] = Field(None, max_length=500, description="风格描述")
    style_features: Optional[Dict[str, Any]] = Field(default={}, description="风格特征")
    is_active: Optional[bool] = Field(True, description="是否激活")
    is_default: Optional[bool] = Field(False, description="是否默认")
    tone: Optional[str] = Field(None, max_length=100, description="语气")
    language_style: Optional[str] = Field(None, max_length=100, description="语言风格")
    sentence_structure: Optional[str] = Field(None, max_length=100, description="句式结构")
    vocabulary_level: Optional[str] = Field(None, max_length=100, description="词汇水平")
    paragraph_length: Optional[str] = Field(None, max_length=100, description="段落长度")
    use_emoji: Optional[bool] = Field(False, description="是否使用emoji")
    use_questions: Optional[bool] = Field(True, description="是否使用问句")
    use_statistics: Optional[bool] = Field(True, description="是否使用数据")


class StyleProfileCreate(StyleProfileBase):
    """风格档案创建模型"""
    pass


class StyleProfileUpdate(BaseModel):
    """风格档案更新模型"""
    name: Optional[str] = Field(None, max_length=100, description="风格名称")
    description: Optional[str] = Field(None, max_length=500, description="风格描述")
    style_features: Optional[Dict[str, Any]] = Field(None, description="风格特征")
    is_active: Optional[bool] = Field(None, description="是否激活")
    is_default: Optional[bool] = Field(None, description="是否默认")
    tone: Optional[str] = Field(None, max_length=100, description="语气")
    language_style: Optional[str] = Field(None, max_length=100, description="语言风格")
    sentence_structure: Optional[str] = Field(None, max_length=100, description="句式结构")
    vocabulary_level: Optional[str] = Field(None, max_length=100, description="词汇水平")
    paragraph_length: Optional[str] = Field(None, max_length=100, description="段落长度")
    use_emoji: Optional[bool] = Field(None, description="是否使用emoji")
    use_questions: Optional[bool] = Field(None, description="是否使用问句")
    use_statistics: Optional[bool] = Field(None, description="是否使用数据")


class StyleProfileInDB(StyleProfileBase):
    """数据库中的风格档案模型"""
    id: int
    user_id: int
    confidence_score: float = 0.0
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class StyleProfileResponse(StyleProfileBase):
    """风格档案响应模型"""
    id: int
    user_id: int
    confidence_score: float = 0.0
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class StyleProfileListResponse(BaseModel):
    """风格档案列表响应模型"""
    items: List[StyleProfileResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ArticleForAnalysisBase(BaseModel):
    """分析文章基础模型"""
    original_url: Optional[str] = Field(None, max_length=1000, description="原始URL")
    title: Optional[str] = Field(None, max_length=500, description="文章标题")
    content: str = Field(..., description="文章内容")
    platform: Optional[str] = Field(None, max_length=50, description="来源平台")
    author: Optional[str] = Field(None, max_length=200, description="作者")
    published_at: Optional[datetime] = Field(None, description="发布时间")


class ArticleForAnalysisCreate(ArticleForAnalysisBase):
    """分析文章创建模型"""
    pass


class ArticleForAnalysisUpdate(BaseModel):
    """分析文章更新模型"""
    original_url: Optional[str] = Field(None, max_length=1000, description="原始URL")
    title: Optional[str] = Field(None, max_length=500, description="文章标题")
    content: Optional[str] = Field(None, description="文章内容")
    platform: Optional[str] = Field(None, max_length=50, description="来源平台")
    author: Optional[str] = Field(None, max_length=200, description="作者")
    published_at: Optional[datetime] = Field(None, description="发布时间")
    is_processed: Optional[bool] = Field(None, description="是否已处理")
    processing_status: Optional[str] = Field(None, description="处理状态")


class ArticleForAnalysisInDB(ArticleForAnalysisBase):
    """数据库中的分析文章模型"""
    id: int
    user_id: int
    word_count: int = 0
    is_processed: bool = False
    processing_status: str = "pending"
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ArticleForAnalysisResponse(ArticleForAnalysisBase):
    """分析文章响应模型"""
    id: int
    user_id: int
    word_count: int = 0
    is_processed: bool = False
    processing_status: str = "pending"
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ArticleForAnalysisListResponse(BaseModel):
    """分析文章列表响应模型"""
    items: List[ArticleForAnalysisResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class StyleAnalysisRequest(BaseModel):
    """风格分析请求模型"""
    content: str = Field(..., description="文章内容")
    title: Optional[str] = Field(None, max_length=500, description="文章标题")


class StyleAnalysisResponse(BaseModel):
    """风格分析响应模型"""
    style_features: Dict[str, Any] = Field(..., description="风格特征")
    summary: str = Field(..., description="分析摘要")
    title: Optional[str] = Field(None, description="文章标题")
    word_count: int = Field(0, description="字数")
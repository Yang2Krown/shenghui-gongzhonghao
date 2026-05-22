from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


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
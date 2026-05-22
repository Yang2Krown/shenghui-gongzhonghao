from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class TopicBase(BaseModel):
    """选题基础模型"""
    title: str = Field(..., max_length=500, description="选题标题")
    content_summary: Optional[str] = Field(None, description="内容摘要")
    source_platform: str = Field(..., description="来源平台")
    source_url: str = Field(..., max_length=1000, description="来源URL")
    category: Optional[str] = Field(None, max_length=100, description="分类")
    heat_score: Optional[int] = Field(0, description="热度分数")
    published_at: Optional[datetime] = Field(None, description="发布时间")
    keywords: Optional[List[str]] = Field(default=[], description="关键词列表")
    image_url: Optional[str] = Field(None, max_length=1000, description="图片URL")
    author: Optional[str] = Field(None, max_length=200, description="作者")
    read_count: Optional[int] = Field(0, description="阅读数")
    like_count: Optional[int] = Field(0, description="点赞数")
    comment_count: Optional[int] = Field(0, description="评论数")


class TopicCreate(TopicBase):
    """选题创建模型"""
    pass


class TopicUpdate(BaseModel):
    """选题更新模型"""
    title: Optional[str] = Field(None, max_length=500, description="选题标题")
    content_summary: Optional[str] = Field(None, description="内容摘要")
    category: Optional[str] = Field(None, max_length=100, description="分类")
    heat_score: Optional[int] = Field(None, description="热度分数")
    keywords: Optional[List[str]] = Field(None, description="关键词列表")
    image_url: Optional[str] = Field(None, max_length=1000, description="图片URL")
    is_processed: Optional[bool] = Field(None, description="是否已处理")


class TopicInDB(TopicBase):
    """数据库中的选题模型"""
    id: int
    scraped_at: datetime
    is_processed: bool = False
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TopicResponse(TopicBase):
    """选题响应模型"""
    id: int
    scraped_at: datetime
    is_processed: bool = False
    created_at: datetime
    updated_at: datetime
    is_collected: Optional[bool] = False
    
    class Config:
        from_attributes = True


class TopicListResponse(BaseModel):
    """选题列表响应模型"""
    items: List[TopicResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TopicCollectionBase(BaseModel):
    """选题收藏基础模型"""
    topic_id: int = Field(..., description="选题ID")
    notes: Optional[str] = Field(None, max_length=500, description="备注")


class TopicCollectionCreate(TopicCollectionBase):
    """选题收藏创建模型"""
    pass


class TopicCollectionInDB(TopicCollectionBase):
    """数据库中的选题收藏模型"""
    id: int
    user_id: int
    collected_at: datetime
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TopicCollectionResponse(TopicCollectionBase):
    """选题收藏响应模型"""
    id: int
    user_id: int
    collected_at: datetime
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TopicFilter(BaseModel):
    """选题筛选模型"""
    category: Optional[str] = Field(None, description="分类筛选")
    platform: Optional[str] = Field(None, description="平台筛选")
    keyword: Optional[str] = Field(None, description="关键词搜索")
    sort_by: str = Field("published_at", description="排序字段")
    sort_order: str = Field("desc", description="排序方式")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")
    min_heat_score: Optional[int] = Field(None, description="最小热度分数")
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class ContentCreationBase(BaseModel):
    """内容创作基础模型"""
    topic_id: Optional[int] = Field(None, description="选题ID")
    title: str = Field(..., max_length=500, description="创作标题")
    content: Optional[str] = Field(None, description="创作内容")
    status: Optional[str] = Field("draft", description="状态")
    style_profile_id: Optional[int] = Field(None, description="风格档案ID")
    tags: Optional[List[str]] = Field(default=[], description="标签列表")
    summary: Optional[str] = Field(None, max_length=1000, description="摘要")
    featured_image: Optional[str] = Field(None, max_length=1000, description="特色图片URL")
    # 选题快照 / 关联
    topic_title: Optional[str] = Field(None, max_length=500, description="选题原标题")
    topic_direction: Optional[str] = Field(None, max_length=100, description="选题方向")
    candidate_id: Optional[int] = Field(None, description="候选选题ID")
    cluster_id: Optional[int] = Field(None, description="话题簇ID")
    outline_id: Optional[int] = Field(None, description="大纲ID")
    # 创作进度
    outline_status: Optional[str] = Field(None, description="大纲生成状态")
    title_status: Optional[str] = Field(None, description="标题生成状态")
    content_status: Optional[str] = Field(None, description="正文生成状态")


class ContentCreationCreate(ContentCreationBase):
    """内容创作创建模型"""
    pass


class ContentCreationUpdate(BaseModel):
    """内容创作更新模型"""
    title: Optional[str] = Field(None, max_length=500, description="创作标题")
    content: Optional[str] = Field(None, description="创作内容")
    status: Optional[str] = Field(None, description="状态")
    style_profile_id: Optional[int] = Field(None, description="风格档案ID")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    summary: Optional[str] = Field(None, max_length=1000, description="摘要")
    featured_image: Optional[str] = Field(None, max_length=1000, description="特色图片URL")
    topic_title: Optional[str] = Field(None, max_length=500)
    topic_direction: Optional[str] = Field(None, max_length=100)
    candidate_id: Optional[int] = None
    cluster_id: Optional[int] = None
    outline_id: Optional[int] = None
    outline_status: Optional[str] = None
    title_status: Optional[str] = None
    content_status: Optional[str] = None


class ContentCreationInDB(ContentCreationBase):
    """数据库中的内容创作模型"""
    id: int
    user_id: int
    word_count: int = 0
    reading_time: int = 0
    published_at: Optional[datetime] = None
    published_platform: Optional[str] = None
    platform_url: Optional[str] = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ContentCreationResponse(ContentCreationBase):
    """内容创作响应模型"""
    id: int
    user_id: int
    word_count: int = 0
    reading_time: int = 0
    published_at: Optional[datetime] = None
    published_platform: Optional[str] = None
    platform_url: Optional[str] = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ContentCreationListResponse(BaseModel):
    """内容创作列表响应模型"""
    items: List[ContentCreationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ContentGenerationRequest(BaseModel):
    """内容生成请求模型"""
    topic_id: Optional[int] = Field(None, description="选题ID")
    topic_title: str = Field(..., max_length=500, description="选题标题")
    topic_summary: Optional[str] = Field(None, description="选题摘要")
    style_profile_id: Optional[int] = Field(None, description="风格档案ID")
    custom_prompt: Optional[str] = Field(None, max_length=1000, description="自定义提示词")
    content_type: str = Field("article", description="内容类型：article, summary, outline")
    
    @validator("content_type")
    def validate_content_type(cls, v):
        """验证内容类型"""
        allowed_types = ["article", "summary", "outline", "social_post"]
        if v not in allowed_types:
            raise ValueError(f"内容类型必须是以下之一: {', '.join(allowed_types)}")
        return v


class ContentGenerationResponse(BaseModel):
    """内容生成响应模型"""
    creation: ContentCreationResponse
    generated_content: str
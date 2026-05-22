"""
任务数据模式

定义任务相关的Pydantic数据模式。
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from app.models.task import TaskStatus


class TaskBase(BaseModel):
    """任务基础模式"""
    title: str = Field(..., max_length=255, description="任务标题")
    description: Optional[str] = Field(None, description="任务描述")


class TaskCreate(TaskBase):
    """任务创建模式"""
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据")


class TaskUpdate(BaseModel):
    """任务更新模式"""
    title: Optional[str] = Field(None, max_length=255, description="任务标题")
    description: Optional[str] = Field(None, description="任务描述")
    status: Optional[TaskStatus] = Field(None, description="任务状态")
    error_message: Optional[str] = Field(None, description="错误信息")


class TaskResponse(TaskBase):
    """任务响应模式"""
    id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    started_at: Optional[datetime] = Field(None, description="开始处理时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")

    class Config:
        """Pydantic配置"""
        from_attributes = True


class TaskListResponse(BaseModel):
    """任务列表响应模式"""
    items: List[TaskResponse] = Field(..., description="任务列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    pages: int = Field(..., description="总页数")

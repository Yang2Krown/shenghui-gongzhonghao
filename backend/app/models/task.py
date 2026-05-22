"""
任务数据模型

定义标题生成任务的数据结构。
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, DateTime, Enum, JSON, Text
from sqlalchemy.sql import func
import enum

from app.db.base import Base


class TaskStatus(str, enum.Enum):
    """任务状态枚举"""
    PENDING = "pending"  # 等待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


class Task(Base):
    """
    标题生成任务模型
    
    存储标题生成任务的基本信息和状态。
    """
    
    __tablename__ = "tasks"
    
    # 主键
    id = Column(String(36), primary_key=True, index=True, comment="任务ID")
    
    # 任务信息
    title = Column(String(255), nullable=False, comment="任务标题")
    description = Column(Text, nullable=True, comment="任务描述")
    status = Column(
        Enum(TaskStatus),
        default=TaskStatus.PENDING,
        nullable=False,
        comment="任务状态",
    )
    
    # 输入数据
    input_data = Column(JSON, nullable=True, comment="输入数据")
    
    # 错误信息
    error_message = Column(Text, nullable=True, comment="错误信息")
    
    # 时间戳
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )
    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="开始处理时间",
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="完成时间",
    )
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"<Task(id={self.id}, status={self.status})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "input_data": self.input_data,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

"""
Agent日志数据模型

记录每个Agent的执行日志，用于调试和优化。
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, DateTime, Integer, Float, JSON, ForeignKey, Text
from sqlalchemy.sql import func

from app.db.base import Base


class AgentLog(Base):
    """
    Agent执行日志模型
    
    记录每个Agent的执行详情，包括输入、输出、耗时等。
    """
    
    __tablename__ = "agent_logs"
    
    # 主键
    id = Column(String(36), primary_key=True, index=True, comment="日志ID")
    task_id = Column(
        String(36),
        ForeignKey("tasks.id"),
        nullable=False,
        comment="任务ID",
    )
    result_id = Column(
        String(36),
        ForeignKey("title_generation_results.id"),
        nullable=True,
        comment="结果ID",
    )
    
    # Agent信息
    agent_type = Column(
        String(20),
        nullable=False,
        comment="Agent类型(A/B/C/D)",
    )
    agent_name = Column(String(50), nullable=False, comment="Agent名称")
    agent_role = Column(String(100), nullable=True, comment="Agent角色描述")
    
    # 执行信息
    execution_order = Column(Integer, nullable=False, comment="执行顺序")
    status = Column(
        String(20),
        default="pending",
        nullable=False,
        comment="执行状态",
    )
    
    # 输入输出
    input_data = Column(JSON, nullable=True, comment="输入数据")
    output_data = Column(JSON, nullable=True, comment="输出数据")
    prompt = Column(Text, nullable=True, comment="提示词")
    raw_response = Column(Text, nullable=True, comment="原始响应")
    
    # 模型信息
    model_name = Column(String(50), nullable=True, comment="使用的模型")
    input_tokens = Column(Integer, nullable=True, comment="输入token数")
    output_tokens = Column(Integer, nullable=True, comment="输出token数")
    estimated_cost = Column(Float, nullable=True, comment="预估成本(USD)")
    
    # 时间信息
    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="开始时间",
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="完成时间",
    )
    duration_seconds = Column(Float, nullable=True, comment="耗时(秒)")
    
    # 错误信息
    error_message = Column(Text, nullable=True, comment="错误信息")
    retry_count = Column(Integer, default=0, nullable=False, comment="重试次数")
    
    # 创建时间
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"<AgentLog(id={self.id}, agent={self.agent_type}, status={self.status})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "result_id": self.result_id,
            "agent_type": self.agent_type,
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "execution_order": self.execution_order,
            "status": self.status,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "prompt": self.prompt,
            "model_name": self.model_name,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost": self.estimated_cost,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

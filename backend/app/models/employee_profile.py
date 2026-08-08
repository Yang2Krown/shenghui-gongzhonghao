"""员工档案模型（P0 团队协作底座）。"""
from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relationship

from app.db.base import BaseModel


class EmployeeProfile(BaseModel):
    """员工档案：与 users 一对一，记录团队内组织信息。"""

    __tablename__ = "employee_profiles"

    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    department = Column(String(50), nullable=True, comment="部门，如 内容/商务/技术")
    position = Column(String(50), nullable=True, comment="岗位")
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="直属上级 user_id")
    employee_no = Column(String(32), nullable=True, comment="工号")
    joined_at = Column(Date, nullable=True, comment="入职日期")
    status = Column(String(20), default="active", nullable=False, comment="active / left")

    user = relationship("User", foreign_keys=[user_id], back_populates="employee_profile")
    manager = relationship("User", foreign_keys=[manager_id])

    def __repr__(self) -> str:
        return f"<EmployeeProfile(user_id={self.user_id}, status='{self.status}')>"

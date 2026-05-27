from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.base import BaseModel, JSONField


class GenerationRecord(BaseModel):
    """AI 生成记录 —— 每次 API 调用写一条，支持双向导航。"""

    __tablename__ = "generation_records"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    type = Column(String(40), nullable=False, index=True)
    run_id = Column(String(100), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default="pending")

    input_snapshot = Column(JSONField, default=dict)
    output_snapshot = Column(JSONField, nullable=True)

    display_title = Column(String(500), nullable=True)

    parent_record_id = Column(
        Integer, ForeignKey("generation_records.id"), nullable=True
    )
    creation_id = Column(
        Integer, ForeignKey("content_creations.id"), nullable=True, index=True
    )
    candidate_id = Column(Integer, nullable=True, index=True)

    resume_context = Column(JSONField, default=dict)

    parent = relationship(
        "GenerationRecord", remote_side="GenerationRecord.id", backref="children"
    )
    user = relationship("User")

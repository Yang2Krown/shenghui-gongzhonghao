"""课程章节表：存储课程资料的结构化内容。"""

from sqlalchemy import Column, Integer, String, Text, Boolean, Index

from app.db.base import BaseModel


class CourseChapter(BaseModel):
    """课程章节——每一章对应一条记录。"""
    __tablename__ = "course_chapters"

    title = Column(String(500), nullable=False, comment="章节标题")
    subtitle = Column(String(200), nullable=True, comment="副标题（侧边栏展示用）")
    kicker = Column(String(50), nullable=True, comment="章节标签，如 '第 1 章' / '附录' / '课程总览'")
    content_html = Column(Text, nullable=True, comment="正文 HTML")
    sort_order = Column(Integer, default=0, nullable=False, index=True, comment="排序序号")
    is_published = Column(Boolean, default=True, nullable=False, comment="是否发布")

    __table_args__ = (
        Index("ix_course_chapters_order", "sort_order"),
    )

    def __repr__(self):
        return f"<CourseChapter(id={self.id}, title='{(self.title or '')[:40]}...')>"

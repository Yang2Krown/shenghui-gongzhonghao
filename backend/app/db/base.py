from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, DateTime, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
from app.core.timezone import utcnow


# 统一 JSON 字段类型：Postgres 自动用 JSONB（可索引），SQLite/其它降级到通用 JSON。
# 用法：Column(JSONField, default=dict)
JSONField = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    """SQLAlchemy基类"""
    pass


class BaseModel(Base):
    """基础模型类"""
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True)
    # 时间戳统一用北京时间（utcnow() 返回 naive 北京时间）；
    # 不能用 func.now()——数据库时区是 UTC，会比北京时间慢 8 小时。
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    
    def to_dict(self):
        """转换为字典"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
    
    def update(self, **kwargs):
        """更新字段"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = utcnow()
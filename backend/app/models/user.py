from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship

from app.db.base import BaseModel
from app.core.timezone import utcnow


class User(BaseModel):
    """用户模型"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    phone = Column(String(20), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(100), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_member = Column(Boolean, default=False, nullable=False, comment="历史会员兼容字段")
    member_since = Column(DateTime, nullable=True, comment="成为会员时间")
    product_access = Column(JSON, default=list, nullable=False, comment="已开通产品权益")
    role = Column(String(20), default="user")  # user, admin, editor
    
    # 时间戳
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    
    # 关系
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    collections = relationship("TopicCollection", back_populates="user", cascade="all, delete-orphan")
    creations = relationship("ContentCreation", back_populates="user", cascade="all, delete-orphan")
    style_profiles = relationship("StyleProfile", back_populates="user", cascade="all, delete-orphan")
    style_sources = relationship("StyleSource", back_populates="user", cascade="all, delete-orphan")
    articles = relationship("ArticleForAnalysis", back_populates="user", cascade="all, delete-orphan")
    employee_profile = relationship(
        "EmployeeProfile",
        back_populates="user",
        uselist=False,
        foreign_keys="EmployeeProfile.user_id",
    )
    meetings_created = relationship(
        "Meeting",
        foreign_keys="Meeting.created_by",
        cascade="all, delete-orphan",
        back_populates="creator",
    )
    meeting_suggestions_owned = relationship(
        "MeetingSuggestion",
        foreign_keys="MeetingSuggestion.owner_id",
        back_populates="owner",
    )
    content_versions_created = relationship(
        "ContentVersion",
        foreign_keys="ContentVersion.created_by",
        back_populates="creator",
        passive_deletes=True,
    )
    experience_cards_created = relationship(
        "ExperienceCard",
        foreign_keys="ExperienceCard.created_by",
        back_populates="creator",
        passive_deletes=True,
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "avatar_url": self.avatar_url,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "is_member": self.is_member,
            "member_since": self.member_since.isoformat() if self.member_since else None,
            "product_access": self.product_access or [],
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None
        }


class UserProfile(BaseModel):
    """用户资料模型"""
    __tablename__ = "user_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    bio = Column(Text, nullable=True)
    persona = Column(Text, nullable=True)
    wechat_id = Column(String(100), nullable=True)
    target_audience = Column(String(200), nullable=True)
    content_style = Column(String(200), nullable=True)
    preferences = Column(JSON, default={})
    
    # 时间戳
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    
    # 关系
    user = relationship("User", back_populates="profile")
    
    def __repr__(self):
        return f"<UserProfile(id={self.id}, user_id={self.user_id})>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "bio": self.bio,
            "persona": self.persona,
            "wechat_id": self.wechat_id,
            "target_audience": self.target_audience,
            "content_style": self.content_style,
            "preferences": self.preferences,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

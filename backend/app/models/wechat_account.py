"""微信公众号账号配置。

一个用户可以绑定多个公众号（AppID / AppSecret），支持设默认。
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import BaseModel


class WechatAccount(BaseModel):
    """用户绑定的微信公众号账号。"""
    __tablename__ = "wechat_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 账号信息
    account_name = Column(String(100), nullable=False, comment="账号别名，方便用户区分多个号")
    appid = Column(String(64), nullable=False, comment="公众号 AppID")
    app_secret = Column(String(128), nullable=False, comment="公众号 AppSecret")
    author = Column(String(32), nullable=True, comment="默认作者名")

    # 默认账号标记
    is_default = Column(Boolean, default=False, nullable=False, comment="是否为默认发布账号")

    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # 关系
    user = relationship("User", backref="wechat_accounts")

    __table_args__ = (
        # 同一用户下账号别名唯一
        UniqueConstraint("user_id", "account_name", name="uq_wechat_account_user_name"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "account_name": self.account_name,
            "appid": self.appid,
            "app_secret": self.app_secret,
            "author": self.author,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

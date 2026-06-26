"""飞书授权绑定。

每个平台用户各自走设备码 OAuth 授权自己的飞书身份，用来读取客户分享的商单 brief 文档。
一个用户对应一条记录（user_id 唯一）。

原生飞书 OAuth：token（user_access_token / refresh_token）直接存本表，按 user_id 隔离，
读文档前按需用 refresh_token 续期。不依赖 lark-cli / 系统钥匙串，Linux 生产可跑。
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import BaseModel


class FeishuAuth(BaseModel):
    """用户的飞书授权绑定（一人一条）。"""
    __tablename__ = "feishu_auths"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 飞书身份信息（授权成功后回填）
    feishu_user_name = Column(String(128), nullable=True, comment="飞书显示名，如「用户054896」")
    feishu_open_id = Column(String(128), nullable=True, comment="飞书 open_id")

    # 状态机：none(未授权) / pending(已发起待用户确认) / valid(已授权) / expired(失效)
    status = Column(String(16), default="none", nullable=False, comment="授权状态")
    scopes = Column(String(512), nullable=True, comment="已授予的 scope")

    # OAuth token（加密存最佳，先与公众号 app_secret 一致存明文；token 比密钥更敏感，列表注意权限）
    access_token = Column(Text, nullable=True, comment="user_access_token")
    refresh_token = Column(Text, nullable=True, comment="refresh_token")
    token_expires_at = Column(DateTime, nullable=True, comment="access_token 过期时间")
    refresh_expires_at = Column(DateTime, nullable=True, comment="refresh_token 过期时间")

    # 设备码流程的临时态
    device_code = Column(String(256), nullable=True, comment="进行中的设备码（pending 时有值）")
    last_error = Column(String(512), nullable=True, comment="最近一次授权失败原因")
    authorized_at = Column(DateTime, nullable=True, comment="最近一次授权成功时间")

    user = relationship("User", backref="feishu_auth")

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_feishu_auth_user"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "feishu_user_name": self.feishu_user_name,
            "feishu_open_id": self.feishu_open_id,
            "status": self.status,
            "scopes": self.scopes,
            # 不输出 token 字段
            "last_error": self.last_error,
            "authorized_at": self.authorized_at.isoformat() if self.authorized_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

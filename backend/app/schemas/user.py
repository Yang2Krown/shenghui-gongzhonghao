from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, validator


class UserBase(BaseModel):
    """用户基础模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: Optional[EmailStr] = Field(None, description="邮箱地址")
    phone: Optional[str] = Field(None, description="手机号")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    avatar_url: Optional[str] = Field(None, description="头像URL")


class UserCreate(UserBase):
    """用户创建模型"""
    password: Optional[str] = Field(None, min_length=6, max_length=100, description="密码")

    @validator("username")
    def validate_username(cls, v):
        """验证用户名"""
        if not v.isalnum() and "_" not in v:
            raise ValueError("用户名只能包含字母、数字和下划线")
        return v


class UserUpdate(BaseModel):
    """用户更新模型"""
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    is_active: Optional[bool] = Field(None, description="是否激活")
    role: Optional[str] = Field(None, description="角色")


class UserInDB(UserBase):
    """数据库中的用户模型"""
    id: int
    hashed_password: str
    is_active: bool = True
    is_superuser: bool = False
    role: str = "user"
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserResponse(UserBase):
    """用户响应模型"""
    id: int
    is_active: bool = True
    is_superuser: bool = False
    role: str = "user"
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserProfileBase(BaseModel):
    """用户资料基础模型"""
    bio: Optional[str] = Field(None, max_length=500, description="个人简介")
    wechat_id: Optional[str] = Field(None, max_length=100, description="微信号")
    target_audience: Optional[str] = Field(None, max_length=200, description="目标受众")
    content_style: Optional[str] = Field(None, max_length=200, description="内容风格")
    preferences: Optional[Dict[str, Any]] = Field(default={}, description="偏好设置")


class UserProfileCreate(UserProfileBase):
    """用户资料创建模型"""
    pass


class UserProfileUpdate(UserProfileBase):
    """用户资料更新模型"""
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    avatar_url: Optional[str] = Field(None, description="头像URL")


class UserProfileInDB(UserProfileBase):
    """数据库中的用户资料模型"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserProfileResponse(UserProfileBase):
    """用户资料响应模型"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """令牌模型"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """令牌负载模型"""
    sub: Optional[int] = None
    type: str = "access"
    exp: Optional[datetime] = None


class TokenRefresh(BaseModel):
    """令牌刷新模型"""
    refresh_token: str


class LoginRequest(BaseModel):
    """登录请求模型"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class PasswordChange(BaseModel):
    """密码修改模型"""
    current_password: str = Field(..., description="当前密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


class SendSmsCodeRequest(BaseModel):
    """发送短信验证码请求"""
    phone: str = Field(..., description="手机号")


class PhoneLoginRequest(BaseModel):
    """手机验证码登录请求"""
    phone: str = Field(..., description="手机号")
    code: str = Field(..., min_length=6, max_length=6, description="6位验证码")
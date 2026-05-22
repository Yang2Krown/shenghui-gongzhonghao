from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    get_password_hash,
    decode_token,
    get_current_user
)
from app.crud.user import user as user_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserResponse,
    Token,
    TokenRefresh,
    LoginRequest,
    SendSmsCodeRequest,
    PhoneLoginRequest,
)
from app.services.sms_service import send_sms_code, verify_sms_code

router = APIRouter()


@router.post("/register", response_model=dict)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """用户注册"""
    # 检查用户名是否已存在
    existing_user = await user_crud.get_by_username(db, username=user_in.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    # 检查邮箱是否已存在
    existing_email = await user_crud.get_by_email(db, email=user_in.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )
    
    # 创建用户
    user = await user_crud.create(db, obj_in=user_in)
    
    # 生成令牌
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    
    return {
        "code": 200,
        "message": "注册成功",
        "data": {
            "user": UserResponse.from_orm(user).dict(),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    }


@router.post("/login", response_model=dict)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """用户登录"""
    # 支持用户名或邮箱登录
    user = None
    if "@" in login_data.username:
        user = await user_crud.get_by_email(db, email=login_data.username)
    else:
        user = await user_crud.get_by_username(db, username=login_data.username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    # 验证密码
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    # 检查用户是否激活
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户未激活"
        )
    
    # 生成令牌
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    
    return {
        "code": 200,
        "message": "登录成功",
        "data": {
            "user": UserResponse.from_orm(user).dict(),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    }


@router.post("/refresh", response_model=dict)
async def refresh_token(
    token_data: TokenRefresh,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """刷新令牌"""
    # 解码刷新令牌
    payload = decode_token(token_data.refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌"
        )
    
    # 检查令牌类型
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌类型"
        )
    
    # 获取用户
    user_id = payload.get("sub")
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 生成新令牌
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    
    return {
        "code": 200,
        "message": "令牌刷新成功",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    }


@router.get("/me", response_model=dict)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> Any:
    """获取当前用户信息"""
    return {
        "code": 200,
        "message": "获取用户信息成功",
        "data": UserResponse.from_orm(current_user).dict()
    }


@router.post("/send-sms-code", response_model=dict)
async def send_sms_code_endpoint(
    req: SendSmsCodeRequest,
) -> Any:
    """发送手机短信验证码"""
    result = await send_sms_code(req.phone)
    if not result["ok"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=result["message"],
        )
    return {"code": 200, "message": result["message"], "data": None}


@router.post("/login-by-phone", response_model=dict)
async def login_by_phone(
    req: PhoneLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """手机验证码登录（不存在则自动注册）"""
    valid = await verify_sms_code(req.phone, req.code)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="验证码错误或已过期",
        )

    user = await user_crud.get_by_phone(db, phone=req.phone)
    if not user:
        user = await user_crud.create_by_phone(db, phone=req.phone)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已被禁用",
        )

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return {
        "code": 200,
        "message": "登录成功",
        "data": {
            "user": UserResponse.from_orm(user).dict(),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
    }


@router.post("/test-token", response_model=dict)
async def test_token(
    current_user: User = Depends(get_current_user)
) -> Any:
    """测试令牌有效性"""
    return {
        "code": 200,
        "message": "令牌有效",
        "data": {
            "user_id": current_user.id,
            "username": current_user.username
        }
    }
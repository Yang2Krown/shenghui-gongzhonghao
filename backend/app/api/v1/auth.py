from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user
)
from app.core.refresh_tokens import (
    RefreshTokenStoreUnavailable,
    is_refresh_token_active,
    register_refresh_token,
    revoke_refresh_token,
    revoke_user_refresh_tokens,
)
from app.crud.user import user as user_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserResponse,
    TokenRefresh,
    LoginRequest,
    SendSmsCodeRequest,
    PhoneLoginRequest,
)
from app.core.sms_service import send_sms_code, verify_sms_code
from app.core.rate_limit import (
    account_actor,
    enforce_rate_limit,
    ip_actor,
    phone_actor,
    rule_from_setting,
)
from app.core.product_access import effective_product_access

router = APIRouter()


async def _ensure_super_admin_by_phone(user: User, db: AsyncSession) -> User:
    """手机号命中配置的最高管理员时，自动授予最高管理员权限。"""
    if user.phone == settings.SUPER_ADMIN_PHONE and (
        not user.is_superuser or user.role != "admin" or user.product_access is None
    ):
        user.is_superuser = True
        user.role = "admin"
        user.product_access = []
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


async def _issue_token_pair(user_id: int) -> dict:
    access_token = create_access_token(subject=user_id)
    refresh_token = create_refresh_token(subject=user_id)
    payload = decode_token(refresh_token)
    if not payload or not payload.get("jti") or not payload.get("exp"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="刷新令牌生成失败",
        )
    try:
        await register_refresh_token(payload["jti"], user_id, payload["exp"])
    except RefreshTokenStoreUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="刷新令牌服务暂不可用，请稍后重试",
        ) from exc
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/register", response_model=dict)
async def register(
    _user_in: UserCreate,
    request: Request,
) -> Any:
    """账号密码注册已下线；统一使用手机号验证码登录/自动注册。"""
    await enforce_rate_limit(
        [rule_from_setting("auth:register:ip", settings.RATE_LIMIT_AUTH_REGISTER_IP, ip_actor(request))],
        request=request,
    )
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="账号密码注册已下线，请使用手机号验证码登录/注册",
    )


@router.post("/login", response_model=dict)
async def login(
    login_data: LoginRequest,
    request: Request,
) -> Any:
    """账号密码登录已下线；统一使用手机号验证码登录/自动注册。"""
    await enforce_rate_limit(
        [
            rule_from_setting("auth:login:ip", settings.RATE_LIMIT_AUTH_LOGIN_IP, ip_actor(request)),
            rule_from_setting("auth:login:account", settings.RATE_LIMIT_AUTH_LOGIN_ACCOUNT, account_actor(login_data.username)),
        ],
        request=request,
    )
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="账号密码登录已下线，请使用手机号验证码登录/注册",
    )


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
    if not payload.get("jti"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )
    
    # 获取用户
    user_id = payload.get("sub")
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户未激活",
        )

    try:
        active = await is_refresh_token_active(payload["jti"], user.id)
    except RefreshTokenStoreUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="刷新令牌服务暂不可用，请稍后重试",
        ) from exc
    if not active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌已失效，请重新登录",
        )

    # 先登记新 token，再撤销旧 token。否则如果登记新 token 时 Redis 短暂故障，
    # 旧 token 已被撤销，客户端就会陷入“刷新失败后只能重新登录”的状态。
    token_pair = await _issue_token_pair(user.id)

    try:
        await revoke_refresh_token(payload["jti"])
    except RefreshTokenStoreUnavailable as exc:
        # 新 token 已经登记成功；撤销旧 token 失败时返回临时错误，客户端会重试，
        # 保留旧 token 可用性，避免一次 Redis 抖动造成不可恢复的登录态。
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="刷新令牌服务暂不可用，请稍后重试",
        ) from exc
    
    return {
        "code": 200,
        "message": "令牌刷新成功",
        "data": token_pair,
    }


@router.post("/logout", response_model=dict)
async def logout(token_data: TokenRefresh) -> Any:
    """登出当前设备：撤销提交的 refresh token。"""
    payload = decode_token(token_data.refresh_token)
    if payload and payload.get("type") == "refresh" and payload.get("jti"):
        try:
            await revoke_refresh_token(payload["jti"])
        except RefreshTokenStoreUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="刷新令牌服务暂不可用，请稍后重试",
            ) from exc
    return {"code": 200, "message": "已登出", "data": None}


@router.post("/logout-all", response_model=dict)
async def logout_all(current_user: User = Depends(get_current_user)) -> Any:
    """全端登出：撤销当前用户所有 refresh token。"""
    try:
        await revoke_user_refresh_tokens(current_user.id)
    except RefreshTokenStoreUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="刷新令牌服务暂不可用，请稍后重试",
        ) from exc
    return {"code": 200, "message": "已全端登出", "data": None}


@router.get("/me", response_model=dict)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> Any:
    """获取当前用户信息"""
    data = UserResponse.from_orm(current_user).dict()
    data["product_access"] = effective_product_access(current_user)
    return {
        "code": 200,
        "message": "获取用户信息成功",
        "data": data
    }


@router.post("/send-sms-code", response_model=dict)
async def send_sms_code_endpoint(
    req: SendSmsCodeRequest,
    request: Request,
) -> Any:
    """发送手机短信验证码"""
    await enforce_rate_limit(
        [
            rule_from_setting("auth:sms:ip", settings.RATE_LIMIT_SMS_IP, ip_actor(request)),
            rule_from_setting("auth:sms:phone", settings.RATE_LIMIT_SMS_PHONE, phone_actor(req.phone)),
        ],
        request=request,
    )

    import logging
    logger = logging.getLogger(__name__)
    try:
        result = await send_sms_code(req.phone)
    except Exception as e:
        logger.error(f"发送验证码异常: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"验证码服务异常: {type(e).__name__}: {e}",
        )
    if not result["ok"]:
        status_code = (
            status.HTTP_429_TOO_MANY_REQUESTS
            if "频繁" in result["message"]
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        raise HTTPException(
            status_code=status_code,
            detail=result["message"],
        )
    return {"code": 200, "message": result["message"], "data": None}


@router.post("/login-by-phone", response_model=dict)
async def login_by_phone(
    req: PhoneLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """手机验证码登录（不存在则自动注册）"""
    await enforce_rate_limit(
        [
            rule_from_setting("auth:login:ip", settings.RATE_LIMIT_AUTH_LOGIN_IP, ip_actor(request)),
            rule_from_setting("auth:login:phone", settings.RATE_LIMIT_AUTH_LOGIN_ACCOUNT, phone_actor(req.phone)),
        ],
        request=request,
    )

    valid = await verify_sms_code(req.phone, req.code)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="验证码错误或已过期",
        )

    user = await user_crud.get_by_phone(db, phone=req.phone)
    if not user:
        user = await user_crud.create_by_phone(db, phone=req.phone)

    user = await _ensure_super_admin_by_phone(user, db)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已被禁用",
        )

    token_pair = await _issue_token_pair(user.id)

    return {
        "code": 200,
        "message": "登录成功",
        "data": {
            "user": UserResponse.from_orm(user).dict(),
            **token_pair,
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

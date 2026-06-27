"""微信公众号账号管理 API。

支持一个用户绑定多个公众号，CRUD + 设默认。
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.wechat_account import WechatAccount

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────

class WechatAccountCreate(BaseModel):
    account_name: str = Field(..., min_length=1, max_length=100, description="账号别名")
    appid: str = Field(..., min_length=1, max_length=64, description="公众号 AppID")
    app_secret: str = Field(..., min_length=1, max_length=128, description="公众号 AppSecret")
    author: Optional[str] = Field(None, max_length=32, description="默认作者名")
    is_default: bool = Field(False, description="是否设为默认账号")


class WechatAccountUpdate(BaseModel):
    account_name: Optional[str] = Field(None, min_length=1, max_length=100)
    appid: Optional[str] = Field(None, min_length=1, max_length=64)
    app_secret: Optional[str] = Field(None, min_length=1, max_length=128)
    author: Optional[str] = Field(None, max_length=32)
    is_default: Optional[bool] = None


# ── 辅助函数 ─────────────────────────────────────────────

async def _clear_default(db: AsyncSession, user_id: int) -> None:
    """清除该用户所有账号的默认标记。"""
    await db.execute(
        update(WechatAccount)
        .where(WechatAccount.user_id == user_id, WechatAccount.is_default.is_(True))
        .values(is_default=False)
    )


async def _get_or_404(db: AsyncSession, user_id: int, account_id: int) -> WechatAccount:
    """获取用户的某个账号，不存在则 404。"""
    result = await db.execute(
        select(WechatAccount).where(
            WechatAccount.id == account_id,
            WechatAccount.user_id == user_id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公众号账号不存在")
    return account


# ── Endpoints ────────────────────────────────────────────

@router.get("", response_model=dict)
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """获取当前用户的所有公众号账号。"""
    result = await db.execute(
        select(WechatAccount)
        .where(WechatAccount.user_id == current_user.id)
        .order_by(WechatAccount.is_default.desc(), WechatAccount.created_at.desc())
    )
    accounts = result.scalars().all()
    return {
        "code": 200,
        "message": "获取成功",
        "data": [a.to_dict() for a in accounts],
    }


@router.post("", response_model=dict)
async def create_account(
    body: WechatAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """新增公众号账号。"""
    # 检查别名是否重复
    existing = await db.execute(
        select(WechatAccount).where(
            WechatAccount.user_id == current_user.id,
            WechatAccount.account_name == body.account_name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"账号别名「{body.account_name}」已存在")

    # 如果设为默认，先清除旧默认
    if body.is_default:
        await _clear_default(db, current_user.id)

    # 如果是该用户的第一个账号，自动设为默认
    count_result = await db.execute(
        select(WechatAccount.id).where(WechatAccount.user_id == current_user.id)
    )
    is_first = len(count_result.all()) == 0

    account = WechatAccount(
        user_id=current_user.id,
        account_name=body.account_name,
        appid=body.appid,
        app_secret=body.app_secret,
        author=body.author,
        is_default=body.is_default or is_first,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    return {"code": 200, "message": "创建成功", "data": account.to_dict()}


@router.put("/{account_id}", response_model=dict)
async def update_account(
    account_id: int,
    body: WechatAccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """更新公众号账号。"""
    account = await _get_or_404(db, current_user.id, account_id)

    # 检查别名冲突
    if body.account_name and body.account_name != account.account_name:
        existing = await db.execute(
            select(WechatAccount).where(
                WechatAccount.user_id == current_user.id,
                WechatAccount.account_name == body.account_name,
                WechatAccount.id != account_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"账号别名「{body.account_name}」已存在")

    # 如果设为默认，先清除旧默认
    if body.is_default and not account.is_default:
        await _clear_default(db, current_user.id)

    # 更新字段
    if body.account_name is not None:
        account.account_name = body.account_name
    if body.appid is not None:
        account.appid = body.appid
    if body.app_secret is not None:
        account.app_secret = body.app_secret
    if body.author is not None:
        account.author = body.author
    if body.is_default is not None:
        account.is_default = body.is_default

    await db.commit()
    await db.refresh(account)

    return {"code": 200, "message": "更新成功", "data": account.to_dict()}


@router.delete("/{account_id}", response_model=dict)
async def delete_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """删除公众号账号。"""
    account = await _get_or_404(db, current_user.id, account_id)

    await db.delete(account)
    await db.commit()

    # 如果删的是默认账号，自动把剩余的第一个设为默认
    if account.is_default:
        result = await db.execute(
            select(WechatAccount)
            .where(WechatAccount.user_id == current_user.id)
            .order_by(WechatAccount.created_at)
            .limit(1)
        )
        next_default = result.scalar_one_or_none()
        if next_default:
            next_default.is_default = True
            await db.commit()

    return {"code": 200, "message": "删除成功"}


@router.put("/{account_id}/set-default", response_model=dict)
async def set_default_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """设为默认公众号。"""
    account = await _get_or_404(db, current_user.id, account_id)

    if account.is_default:
        return {"code": 200, "message": "已是默认账号", "data": account.to_dict()}

    await _clear_default(db, current_user.id)
    account.is_default = True
    await db.commit()
    await db.refresh(account)

    return {"code": 200, "message": "已设为默认", "data": account.to_dict()}


@router.post("/{account_id}/test", response_model=dict)
async def test_account_connection(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """测试某个公众号账号的连接。"""
    account = await _get_or_404(db, current_user.id, account_id)

    from app.services.wechat.wechat_draft_service import get_access_token

    try:
        access_token = await get_access_token(account.appid, account.app_secret)
        return {
            "code": 200,
            "message": "连接成功",
            "data": {"success": True, "message": "公众号凭证验证通过"},
        }
    except ValueError as e:
        return {
            "code": 400,
            "message": "连接失败",
            "data": {"success": False, "message": str(e)},
        }

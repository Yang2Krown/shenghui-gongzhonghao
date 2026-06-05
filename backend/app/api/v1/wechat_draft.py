"""
微信公众号草稿箱 API
发布文章到微信公众号草稿箱
"""
import logging
import base64
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


class WechatDraftRequest(BaseModel):
    title: str = Field("", description="文章标题")
    content: str = Field(..., description="文章正文（纯文本或 HTML 均可）")
    author: Optional[str] = Field(None, description="作者")
    digest: Optional[str] = Field(None, description="摘要")
    appid: str = Field(..., description="公众号 AppID")
    app_secret: str = Field(..., description="公众号 AppSecret")
    cover_image_url: Optional[str] = Field(None, description="封面图 URL（远程）")
    cover_image_base64: Optional[str] = Field(None, description="封面图 Base64 编码")
    content_source_url: Optional[str] = Field(None, description="原文链接")
    need_open_comment: int = Field(0, description="是否打开评论（0 关闭 1 打开）")
    only_fans_can_comment: int = Field(0, description="是否仅粉丝可评论（0 否 1 是）")


class WechatDraftResponse(BaseModel):
    success: bool
    media_id: Optional[str] = None
    item_id: Optional[str] = None
    message: str = ""


class GenerateCoverRequest(BaseModel):
    title: str = Field("", description="文章标题，用于生成封面提示词")
    content: str = Field("", description="文章正文，用于生成封面提示词")
    style: Optional[str] = Field(None, description="封面风格描述，如：简约、科技、温暖")


@router.post("/create-draft")
async def create_wechat_draft(
    request: WechatDraftRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """发布文章到微信公众号草稿箱"""
    from app.services.wechat_draft_service import (
        get_access_token,
        upload_permanent_image,
        create_draft,
        generate_default_cover,
    )
    import httpx

    try:
        # 0. 日志：打印收到的请求
        logger.info(f"[WeChatDraft] 收到请求 title={request.title!r} ({len(request.title)}字符), content长度={len(request.content)}字符")

        # 1. 获取 access_token
        access_token = await get_access_token(request.appid, request.app_secret)

        # 2. 上传封面图
        thumb_media_id = ""
        if request.cover_image_base64:
            # Base64 → bytes
            if "," in request.cover_image_base64:
                request.cover_image_base64 = request.cover_image_base64.split(",", 1)[1]
            image_data = base64.b64decode(request.cover_image_base64)
            thumb_media_id = await upload_permanent_image(
                access_token, image_data, "cover.jpg"
            )
        elif request.cover_image_url:
            # 远程 URL → bytes
            async with httpx.AsyncClient(timeout=15, verify=False) as client:
                resp = await client.get(request.cover_image_url)
                resp.raise_for_status()
                image_data = resp.content
            thumb_media_id = await upload_permanent_image(
                access_token, image_data, "cover.jpg"
            )
        else:
            # 无封面图 → 根据标题自动生成默认封面
            logger.info("[WeChatDraft] 未提供封面图，自动生成默认封面")
            cover_data = generate_default_cover(request.title)
            thumb_media_id = await upload_permanent_image(
                access_token, cover_data, "default_cover.png"
            )

        # 3. 如果没有标题，从正文自动截取前 30 字
        title = request.title.strip()
        if not title:
            import re as _re
            plain = _re.sub(r'<[^>]+>', '', request.content).strip()
            title = plain[:30] + ('…' if len(plain) > 30 else '')
            if not title:
                title = "未命名文章"

        # 4. 创建草稿
        result = await create_draft(
            access_token=access_token,
            title=title,
            content=request.content,
            author=request.author or "",
            digest=request.digest or "",
            thumb_media_id=thumb_media_id,
            content_source_url=request.content_source_url or "",
            need_open_comment=request.need_open_comment,
            only_fans_can_comment=request.only_fans_can_comment,
        )

        return {
            "code": 200,
            "message": "草稿创建成功",
            "data": {
                "success": True,
                "media_id": result.media_id,
                "item_id": result.item_id,
                "message": "文章已保存到公众号草稿箱",
            },
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建微信草稿失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建草稿失败: {str(e)[:200]}")


@router.post("/test-connection")
async def test_wechat_connection(
    appid: str,
    app_secret: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """测试公众号连接（验证 AppID/Secret 是否正确）"""
    from app.services.wechat_draft_service import get_access_token

    try:
        access_token = await get_access_token(appid, app_secret)
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


@router.post("/generate-cover")
async def generate_cover(
    request: GenerateCoverRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """用 AI 根据文章标题生成封面图"""
    from app.services.wechat_draft_service import generate_ai_cover

    try:
        image_url = await generate_ai_cover(
            title=request.title,
            content=request.content,
            style=request.style or "",
        )
        return {
            "code": 200,
            "message": "封面生成成功",
            "data": {"url": image_url},
        }
    except Exception as e:
        logger.error(f"AI 封面生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"封面生成失败: {str(e)[:200]}")

"""
微信公众号草稿箱 API
发布文章到微信公众号草稿箱
"""
import logging
import base64
import re
import asyncio
import httpx
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


async def _upload_images_to_wechat(access_token: str, html_content: str) -> str:
    """
    将 HTML 中的图片上传到微信，获取微信可识别的 URL

    :param access_token: 微信 access_token
    :param html_content: HTML 内容
    :return: 替换后的 HTML 内容
    """
    from app.services.wechat.wechat_draft_service import upload_content_image

    # 匹配所有 img 标签的 src
    img_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)

    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        async def replace_img_url(match):
            original_url = match.group(1)

            # 跳过已经是微信 URL 的图片
            if 'mmbiz.qpic.cn' in original_url or 'mmbiz.qlogo.cn' in original_url:
                return match.group(0)

            try:
                # 下载图片
                resp = await client.get(original_url, follow_redirects=True)
                resp.raise_for_status()

                # 获取文件名
                filename = original_url.split('/')[-1].split('?')[0]
                if not filename or '.' not in filename:
                    content_type = resp.headers.get('content-type', 'image/jpeg')
                    ext_map = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/gif': '.gif'}
                    ext = ext_map.get(content_type, '.jpg')
                    filename = f"image_{hash(original_url) & 0xFFFFFFFF:08x}{ext}"

                # 上传到微信
                wechat_url = await upload_content_image(
                    access_token=access_token,
                    image_data=resp.content,
                    filename=filename,
                )

                logger.info(f"图片已上传到微信: {original_url[:50]}... -> {wechat_url[:50]}...")
                return match.group(0).replace(original_url, wechat_url)

            except Exception as e:
                logger.warning(f"上传图片到微信失败: {original_url[:50]}... - {e}")
                # 上传失败，保留原 URL
                return match.group(0)

        # 异步替换所有图片 URL
        tasks = []
        for match in img_pattern.finditer(html_content):
            tasks.append(replace_img_url(match))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # 按顺序替换（从后往前，避免索引偏移）
            for i, (match, result) in enumerate(zip(img_pattern.finditer(html_content), results)):
                if isinstance(result, str):
                    html_content = html_content.replace(match.group(0), result, 1)

    return html_content


async def _resolve_credentials(
    db: AsyncSession,
    user: User,
    account_id: Optional[int],
    appid: Optional[str],
    app_secret: Optional[str],
) -> tuple:
    """解析公众号凭证：优先 account_id，其次 appid+app_secret。"""
    if account_id is not None:
        from app.models.wechat_account import WechatAccount
        result = await db.execute(
            select(WechatAccount).where(
                WechatAccount.id == account_id,
                WechatAccount.user_id == user.id,
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            raise ValueError("公众号账号不存在")
        return account.appid, account.app_secret

    if appid and app_secret:
        return appid, app_secret

    # 如果都没传，尝试用用户的默认账号
    from app.models.wechat_account import WechatAccount
    result = await db.execute(
        select(WechatAccount).where(
            WechatAccount.user_id == user.id,
            WechatAccount.is_default.is_(True),
        )
    )
    default = result.scalar_one_or_none()
    if default:
        return default.appid, default.app_secret

    raise ValueError("未提供公众号凭证，请先在设置页面配置公众号账号")


class WechatDraftRequest(BaseModel):
    title: str = Field("", description="文章标题")
    content: str = Field(..., description="文章正文（纯文本或 HTML 均可）")
    author: Optional[str] = Field(None, description="作者")
    digest: Optional[str] = Field(None, description="摘要")
    account_id: Optional[int] = Field(None, description="公众号账号 ID（优先使用）")
    appid: Optional[str] = Field(None, description="公众号 AppID（account_id 为空时使用）")
    app_secret: Optional[str] = Field(None, description="公众号 AppSecret（account_id 为空时使用）")
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """发布文章到微信公众号草稿箱"""
    from app.services.wechat.wechat_draft_service import (
        get_access_token,
        upload_permanent_image,
        create_draft,
        generate_default_cover,
    )
    import httpx

    try:
        # 0. 解析凭证：优先 account_id，其次 appid+app_secret
        appid, app_secret = await _resolve_credentials(db, current_user, request.account_id, request.appid, request.app_secret)

        # 0.1 日志：打印收到的请求
        logger.info(f"[WeChatDraft] 收到请求 title={request.title!r} ({len(request.title)}字符), content长度={len(request.content)}字符")

        # 1. 获取 access_token
        access_token = await get_access_token(appid, app_secret)

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

        # 4. 处理正文中的图片：将非微信 URL 的图片上传到微信
        logger.info("[WeChatDraft] 开始处理正文图片...")
        content = await _upload_images_to_wechat(access_token, request.content)
        logger.info(f"[WeChatDraft] 图片处理完成，content长度={len(content)}字符")

        # 5. 创建草稿
        result = await create_draft(
            access_token=access_token,
            title=title,
            content=content,
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
    account_id: Optional[int] = None,
    appid: Optional[str] = None,
    app_secret: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """测试公众号连接（验证 AppID/Secret 是否正确）"""
    from app.services.wechat.wechat_draft_service import get_access_token

    try:
        resolved_appid, resolved_secret = await _resolve_credentials(db, current_user, account_id, appid, app_secret)
        access_token = await get_access_token(resolved_appid, resolved_secret)
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


@router.get("/bing-images")
async def get_bing_images(
    n: int = 15,
    current_user: User = Depends(get_current_user),
) -> dict:
    """获取 Bing 每日一图列表（最近 n 张，横屏 1920×1080）。

    通过后端代理 Bing 官方 HPImageArchive 接口，避免前端直接请求的 CORS 问题。
    官方单次最多返回 8 张、idx 最多翻到 8，因此分页请求并按日期去重，最多约 15 天。
    """
    import httpx

    n = max(1, min(n, 15))  # Bing 官方约能回溯 15 天
    try:
        raw_items = []
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            for idx in (0, 8):
                api_url = (
                    "https://www.bing.com/HPImageArchive.aspx"
                    f"?format=js&idx={idx}&n=8&mkt=zh-CN"
                )
                resp = await client.get(api_url)
                resp.raise_for_status()
                raw_items.extend(resp.json().get("images", []))
                if len(raw_items) >= n + 1:
                    break

        images = []
        seen_dates = set()
        for item in raw_items:
            sd = item.get("startdate", "")
            if sd in seen_dates:  # 分页之间会有重叠，按日期去重
                continue
            seen_dates.add(sd)
            url_base = item.get("urlbase", "")
            # urlbase 形如 /th?id=OHR.xxx，拼成 1920×1080 横屏图
            if url_base:
                full_url = f"https://www.bing.com{url_base}_1920x1080.jpg"
            else:
                full_url = f"https://www.bing.com{item.get('url', '')}"
            # startdate 形如 20240613 → 2024-06-13
            date = f"{sd[:4]}-{sd[4:6]}-{sd[6:]}" if len(sd) == 8 else sd
            images.append({
                "url": full_url,
                "title": item.get("copyright", "") or item.get("title", ""),
                "date": date,
            })
            if len(images) >= n:
                break

        return {
            "code": 200,
            "message": "获取成功",
            "data": {"images": images},
        }
    except Exception as e:
        logger.error(f"获取 Bing 每日一图失败: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="获取每日一图失败，请重试")


@router.post("/generate-cover")
async def generate_cover(
    request: GenerateCoverRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """用 AI 根据文章标题生成封面图"""
    from app.services.wechat.wechat_draft_service import generate_ai_cover

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

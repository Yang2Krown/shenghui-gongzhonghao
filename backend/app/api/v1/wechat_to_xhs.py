"""
公众号转小红书 - API 路由
"""
import asyncio
import os
import uuid
import logging
from typing import Optional, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.models.user import User
from app.services.wechat_to_xhs_service import generate_xhs_content
from app.services.link_extractor import extract_wechat, extract_wechat_with_images
from app.services import oss_uploader
from app.services.generation_tracker import track_start, track_complete, track_fail

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_BASE = os.path.abspath("./uploads")

# 中转图片保留时长（小时）：图片只用于「下载→传给小红书」，用完即弃。
# 超过该时长的批次目录会在下次提取时被清理，避免磁盘越积越多。
WECHAT_IMAGE_TTL_HOURS = int(os.environ.get("WECHAT_IMAGE_TTL_HOURS", "24"))


def _cleanup_old_image_batches(max_age_hours: int = WECHAT_IMAGE_TTL_HOURS) -> int:
    """删除 wechat_images 下超过 max_age_hours 的批次目录。返回删除的目录数。"""
    import shutil
    import time as _time

    base = os.path.join(UPLOAD_BASE, "wechat_images")
    if not os.path.isdir(base):
        return 0

    cutoff = _time.time() - max_age_hours * 3600
    removed = 0
    try:
        for entry in os.scandir(base):
            if not entry.is_dir():
                continue
            try:
                if entry.stat().st_mtime < cutoff:
                    shutil.rmtree(entry.path, ignore_errors=True)
                    removed += 1
            except OSError:
                continue
    except OSError as e:
        logger.warning(f"[cleanup] 扫描图片目录失败: {e}")
    if removed:
        logger.info(f"[cleanup] 已清理 {removed} 个过期图片批次（>{max_age_hours}h）")
    return removed

WECHAT_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.42(0x18002a2e) "
    "NetType/WIFI Language/zh_CN"
)


class ContentConvertRequest(BaseModel):
    """粘贴内容转换请求"""
    content: str = Field(..., min_length=10, description="公众号文章内容")
    original_title: Optional[str] = Field(None, description="原文章标题")


class LinkConvertRequest(BaseModel):
    """链接提取转换请求"""
    url: str = Field(..., description="公众号文章链接")


class ExtractPreviewRequest(BaseModel):
    """链接图文提取请求"""
    url: str = Field(..., description="公众号文章链接")


@router.post("/convert-content")
async def convert_content(
    request: ContentConvertRequest,
    current_user: User = Depends(get_current_user),
):
    """
    将粘贴的公众号内容转换为小红书风格
    """
    if not request.content or len(request.content.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="内容太短，请提供至少10个字符的内容"
        )

    run_id = f"xhs-{uuid.uuid4().hex[:12]}"
    await track_start(
        user_id=current_user.id,
        type="xhs_convert",
        run_id=run_id,
        input_snapshot={"content_length": len(request.content), "original_title": request.original_title},
        display_title=f"转小红书 · {(request.original_title or request.content[:20])}",
        resume_context={"route": "/wechat-to-xhs", "query": {}},
    )

    result = await generate_xhs_content(
        content=request.content,
        original_title=request.original_title
    )

    if not result.get("success"):
        await track_fail(run_id, result.get("error", "未知错误"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成失败: {result.get('error', '未知错误')}"
        )

    await track_complete(run_id, result["data"])

    return {
        "code": 200,
        "message": "转换成功",
        "data": result["data"]
    }


@router.post("/convert-link")
async def convert_link(
    request: LinkConvertRequest,
    current_user: User = Depends(get_current_user),
):
    """
    从公众号链接提取内容并转换为小红书风格
    """
    if not request.url or not request.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请输入公众号链接"
        )

    url = request.url.strip()
    if 'mp.weixin.qq.com' not in url and 'weixin.qq.com' not in url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请输入有效的微信公众号链接（mp.weixin.qq.com）"
        )

    run_id = f"xhs-link-{uuid.uuid4().hex[:12]}"
    await track_start(
        user_id=current_user.id,
        type="xhs_convert",
        run_id=run_id,
        input_snapshot={"url": url},
        display_title=f"转小红书(链接) · {url[:30]}",
        resume_context={"route": "/wechat-to-xhs", "query": {}},
    )

    try:
        extracted = await extract_wechat(url)
    except Exception as e:
        await track_fail(run_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"提取公众号内容失败: {str(e)}"
        )

    if not extracted.get("content"):
        error_msg = extracted.get("content", "无法提取文章内容")
        await track_fail(run_id, error_msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    result = await generate_xhs_content(
        content=extracted["content"],
        original_title=extracted.get("title")
    )

    if not result.get("success"):
        await track_fail(run_id, result.get("error", "未知错误"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成失败: {result.get('error', '未知错误')}"
        )

    response_data = {
        **result["data"],
        "original_title": extracted.get("title"),
        "original_author": extracted.get("author")
    }
    await track_complete(run_id, response_data, display_title=f"转小红书 · {extracted.get('title', '')[:30]}")

    return {
        "code": 200,
        "message": "转换成功",
        "data": response_data
    }


@router.post("/extract-link-preview")
async def extract_link_preview(
    request: ExtractPreviewRequest,
    current_user: User = Depends(get_current_user),
):
    """
    提取公众号链接的图文内容（含图片位置），下载图片到本地代理。
    返回结构化 blocks 列表（text/image 类型）。
    """
    url = request.url.strip()
    if 'mp.weixin.qq.com' not in url and 'weixin.qq.com' not in url:
        raise HTTPException(status_code=400, detail="请输入有效的微信公众号链接")

    # 提取新文章前，顺手清掉过期的中转图片，避免磁盘越积越多
    _cleanup_old_image_batches()

    extracted = await extract_wechat_with_images(url)
    if extracted.get("error"):
        raise HTTPException(status_code=400, detail=extracted["error"])

    blocks = extracted.get("blocks", [])
    if not blocks:
        raise HTTPException(status_code=400, detail="未能提取到文章内容")

    image_urls = [b["url"] for b in blocks if b["type"] == "image" and b.get("url")]
    local_map = {}
    oss_map = {}

    if image_urls:
        batch_id = uuid.uuid4().hex[:12]
        batch_dir = os.path.join(UPLOAD_BASE, "wechat_images", batch_id)
        os.makedirs(batch_dir, exist_ok=True)

        headers = {
            "User-Agent": WECHAT_UA,
            "Referer": "https://mp.weixin.qq.com/",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        }

        oss_configured = oss_uploader.is_oss_configured()
        logger.info(f"[OSS] OSS 配置状态: {oss_configured}, endpoint={oss_uploader._endpoint}, bucket={oss_uploader._bucket_name}")
        if oss_configured:
            logger.info("[OSS] OSS 已配置，图片将上传到 OSS")

        # 先并发下载所有微信图片
        downloaded = {}  # img_url -> (content, content_type)
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, verify=False) as client:
            async def download_one(idx, img_url):
                try:
                    resp = await client.get(img_url, headers=headers)
                    resp.raise_for_status()
                    ct = resp.headers.get("content-type", "")
                    ext = ".jpg"
                    for mime, e in {"image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}.items():
                        if mime in ct:
                            ext = e
                            break
                    filename = f"{idx:03d}_{uuid.uuid4().hex[:8]}{ext}"
                    filepath = os.path.join(batch_dir, filename)
                    with open(filepath, "wb") as f:
                        f.write(resp.content)
                    local_map[img_url] = f"/uploads/wechat_images/{batch_id}/{filename}"
                    return img_url, resp.content, ct, filename
                except Exception as e:
                    logger.warning(f"下载图片失败: {img_url} - {e}")
                    return img_url, None, "", ""

            results = await asyncio.gather(*[download_one(i, u) for i, u in enumerate(image_urls)])
            for img_url, content, ct, filename in results:
                if content:
                    downloaded[img_url] = (content, ct, filename)

        # 并发上传到 OSS（在线程池中运行同步代码）
        logger.info(f"[OSS] 下载完成: {len(downloaded)}/{len(image_urls)} 张成功")
        if oss_configured and downloaded:
            async def upload_one(img_url, content, ct, filename):
                oss_filename = f"{batch_id}/{filename}"
                logger.info(f"[OSS] 正在上传: {oss_filename} ({len(content)} bytes)")
                oss_url = await asyncio.to_thread(oss_uploader.upload_bytes, content, oss_filename, ct)
                return img_url, oss_url

            upload_results = await asyncio.gather(*[
                upload_one(url, data, ct, fn)
                for url, (data, ct, fn) in downloaded.items()
            ])
            for img_url, oss_url in upload_results:
                if oss_url:
                    oss_map[img_url] = oss_url
                    logger.info(f"[OSS] 图片上传成功: {oss_url[:80]}...")
                else:
                    logger.warning(f"[OSS] 图片上传失败: {img_url}")
        else:
            logger.warning(f"[OSS] 跳过上传: configured={oss_configured}, downloaded={len(downloaded)}")

    for block in blocks:
        if block["type"] == "image" and block.get("url") in local_map:
            block["local_path"] = local_map[block["url"]]
            # 优先使用 OSS 公网 URL
            if block["url"] in oss_map:
                block["url"] = oss_map[block["url"]]

    return {
        "code": 200,
        "data": {
            "title": extracted.get("title", ""),
            "author": extracted.get("author", ""),
            "blocks": blocks,
            "tags": extracted.get("tags", []),
            "image_count": len(local_map),
            "text_content": '\n\n'.join(b["content"] for b in blocks if b["type"] == "text"),
        }
    }

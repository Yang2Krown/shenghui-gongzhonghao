"""
图片代理下载 - 解决微信防盗链
"""
import os
import uuid
import logging
from typing import List

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

WECHAT_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.42(0x18002a2e) "
    "NetType/WIFI Language/zh_CN"
)

UPLOAD_BASE = os.path.abspath("./uploads")


class BatchDownloadRequest(BaseModel):
    urls: List[str] = Field(..., description="图片 URL 列表")
    referer: str = Field(default="https://mp.weixin.qq.com/", description="Referer 头")


class BatchDownloadResponse(BaseModel):
    images: List[dict]


def _guess_ext(url: str, content_type: str = "") -> str:
    from urllib.parse import urlparse
    path = urlparse(url).path
    if '.' in path.split('/')[-1]:
        ext = '.' + path.split('/')[-1].rsplit('.', 1)[-1].split('?')[0].lower()
        if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'):
            return ext
    ct_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}
    for mime, ext in ct_map.items():
        if mime in content_type:
            return ext
    return ".jpg"


@router.post("/download-batch")
async def download_batch(
    request: BatchDownloadRequest,
    current_user: User = Depends(get_current_user),
):
    batch_id = uuid.uuid4().hex[:12]
    batch_dir = os.path.join(UPLOAD_BASE, "wechat_images", batch_id)
    os.makedirs(batch_dir, exist_ok=True)

    results = []
    headers = {
        "User-Agent": WECHAT_UA,
        "Referer": request.referer,
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    }

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, verify=False) as client:
        for i, url in enumerate(request.urls):
            try:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                ext = _guess_ext(url, resp.headers.get("content-type", ""))
                filename = f"{i:03d}_{uuid.uuid4().hex[:8]}{ext}"
                filepath = os.path.join(batch_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                local_path = f"/uploads/wechat_images/{batch_id}/{filename}"
                results.append({"original_url": url, "local_path": local_path, "success": True})
                logger.info(f"下载图片成功: {url} -> {local_path}")
            except Exception as e:
                logger.warning(f"下载图片失败: {url} - {e}")
                results.append({"original_url": url, "local_path": "", "success": False, "error": str(e)[:100]})

    return {"code": 200, "data": {"batch_id": batch_id, "images": results}}

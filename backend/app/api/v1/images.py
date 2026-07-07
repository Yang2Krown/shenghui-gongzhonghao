"""
图片上传 API
支持上传图片到 OSS，返回可访问的 URL
"""
import logging
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from app.core.security import get_current_user
from app.core.rate_limit import limit_file_upload
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

# 配置项
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGES_PER_USER = 500  # 每用户最多 500 张图片
IMAGE_EXPIRY_DAYS = 30  # 图片保留 30 天


class ImageUploadResponse(BaseModel):
    url: str
    filename: str
    size: int
    expires_at: Optional[str] = None


async def _count_user_images(user_prefix: str) -> int:
    """统计用户已上传的图片数量"""
    try:
        import oss2
        from app.core.oss_uploader import (
            _access_key_id,
            _access_key_secret,
            _endpoint,
            _bucket_name,
        )

        if not all([_access_key_id, _access_key_secret, _endpoint, _bucket_name]):
            return 0

        auth = oss2.Auth(_access_key_id, _access_key_secret)
        bucket = oss2.Bucket(auth, _endpoint, _bucket_name)

        count = 0
        for obj in oss2.ObjectIterator(bucket, prefix=user_prefix):
            count += 1
            if count >= MAX_IMAGES_PER_USER:
                break

        return count
    except Exception as e:
        logger.warning(f"统计用户图片数量失败: {e}")
        return 0


async def _cleanup_old_images():
    """清理过期图片（可由定时任务调用）"""
    try:
        import oss2
        from app.core.oss_uploader import (
            _access_key_id,
            _access_key_secret,
            _endpoint,
            _bucket_name,
            _dir,
        )

        if not all([_access_key_id, _access_key_secret, _endpoint, _bucket_name]):
            return

        auth = oss2.Auth(_access_key_id, _access_key_secret)
        bucket = oss2.Bucket(auth, _endpoint, _bucket_name)

        cutoff = datetime.now() - timedelta(days=IMAGE_EXPIRY_DAYS)
        deleted_count = 0

        for obj in oss2.ObjectIterator(bucket, prefix=f"{_dir}/"):
            # 获取文件修改时间
            last_modified = datetime.fromtimestamp(obj.last_modified)
            if last_modified < cutoff:
                bucket.delete_object(obj.key)
                deleted_count += 1

        if deleted_count > 0:
            logger.info(f"已清理 {deleted_count} 张过期图片")

    except Exception as e:
        logger.error(f"清理过期图片失败: {e}")


@router.post("/upload", response_model=ImageUploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(limit_file_upload),
):
    """
    上传图片到 OSS

    支持格式：JPEG, PNG, GIF, WebP
    最大尺寸：10MB
    每用户最多：100 张图片
    """
    # 验证文件类型
    if not file.content_type or file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片格式: {file.content_type}，支持: JPEG, PNG, GIF, WebP"
        )

    # 检查用户上传数量限制
    from app.core.oss_uploader import _bucket_name, _dir
    user_prefix = f"{_dir}/{current_user.id}/"
    user_image_count = await _count_user_images(user_prefix)
    if user_image_count >= MAX_IMAGES_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"已达到上传上限（{MAX_IMAGES_PER_USER} 张），请删除部分图片后再上传"
        )

    # 读取文件内容
    data = await file.read()

    # 验证文件大小
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"图片大小超过限制: {len(data) / 1024 / 1024:.1f}MB，最大: 10MB"
        )

    # 上传到 OSS
    from app.core.oss_uploader import upload_bytes, is_oss_configured, _dir

    if not is_oss_configured():
        raise HTTPException(
            status_code=500,
            detail="OSS 未配置，请在环境变量中设置 OSS_ACCESS_KEY_ID 等参数"
        )

    try:
        # 按用户 ID 分目录存储，便于管理和清理
        user_dir = f"{_dir}/{current_user.id}"
        url = upload_bytes(
            data=data,
            filename=file.filename or "image.jpg",
            content_type=file.content_type,
            dir_prefix=user_dir,
        )

        if not url:
            raise HTTPException(status_code=500, detail="OSS 上传失败")

        logger.info(f"图片上传成功: {file.filename} -> {url[:50]}...")

        # 计算过期时间
        expires_at = (datetime.now() + timedelta(days=IMAGE_EXPIRY_DAYS)).isoformat()

        return ImageUploadResponse(
            url=url,
            filename=file.filename or "image.jpg",
            size=len(data),
            expires_at=expires_at,
        )

    except Exception as e:
        logger.error(f"图片上传失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"图片上传失败: {str(e)[:200]}")


@router.post("/upload-to-wechat")
async def upload_image_to_wechat(
    file: UploadFile = File(...),
    account_id: Optional[int] = None,
    current_user: User = Depends(limit_file_upload),
):
    """
    上传图片到微信公众号（临时素材）

    用于获取微信可识别的图片 URL，发布草稿时使用
    """
    from app.api.v1.wechat_draft import _resolve_credentials
    from app.services.wechat.wechat_draft_service import (
        get_access_token,
        upload_content_image,
    )
    from app.db.session import get_db
    from sqlalchemy.ext.asyncio import AsyncSession

    # 验证文件类型
    if not file.content_type or file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片格式: {file.content_type}"
        )

    # 读取文件内容
    data = await file.read()

    # 获取数据库会话
    async for db in get_db():
        try:
            # 解析公众号凭证
            appid, app_secret = await _resolve_credentials(
                db, current_user, account_id, None, None
            )

            # 获取 access_token
            access_token = await get_access_token(appid, app_secret)

            # 上传到微信
            url = await upload_content_image(
                access_token=access_token,
                image_data=data,
                filename=file.filename or "image.jpg",
            )

            logger.info(f"图片上传到微信成功: {file.filename} -> {url[:50]}...")

            return {
                "code": 200,
                "data": {
                    "url": url,
                    "filename": file.filename,
                    "size": len(data),
                },
            }

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"上传到微信失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"上传失败: {str(e)[:200]}")
        finally:
            await db.close()

    raise HTTPException(status_code=500, detail="数据库连接失败")


@router.get("/stats")
async def get_image_stats(
    current_user: User = Depends(get_current_user),
):
    """获取用户图片统计信息"""
    from app.core.oss_uploader import _dir

    user_prefix = f"{_dir}/{current_user.id}/"
    image_count = await _count_user_images(user_prefix)

    return {
        "code": 200,
        "data": {
            "total_images": image_count,
            "max_images": MAX_IMAGES_PER_USER,
            "remaining": MAX_IMAGES_PER_USER - image_count,
            "expiry_days": IMAGE_EXPIRY_DAYS,
        },
    }


@router.post("/cleanup")
async def cleanup_old_images(
    current_user: User = Depends(get_current_user),
):
    """清理过期图片（管理员或定时任务调用）"""
    # 这里可以添加管理员权限检查
    await _cleanup_old_images()
    return {
        "code": 200,
        "message": "清理任务已启动",
    }

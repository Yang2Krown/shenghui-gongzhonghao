"""
阿里云 OSS 上传工具
用于将图片上传到 OSS 并返回公网可访问的签名 URL
"""
import os
import uuid
import mimetypes
from typing import Optional

from dotenv import load_dotenv

# 确保 .env 文件被加载
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

import oss2


_access_key_id = os.getenv("OSS_ACCESS_KEY_ID", "")
_access_key_secret = os.getenv("OSS_ACCESS_KEY_SECRET", "")
_endpoint = os.getenv("OSS_ENDPOINT", "")
_bucket_name = os.getenv("OSS_BUCKET_NAME", "")
_dir = os.getenv("OSS_DIR", "gzh-images")


def is_oss_configured() -> bool:
    return bool(_access_key_id and _access_key_secret and _endpoint and _bucket_name)


def upload_bytes(data: bytes, filename: str, content_type: str = "") -> Optional[str]:
    """上传字节数据到 OSS，返回签名 URL（10 年有效期）。"""
    if not is_oss_configured():
        return None

    if not content_type:
        content_type = mimetypes.guess_type(filename)[0] or "image/jpeg"

    key = f"{_dir.rstrip('/')}/{filename}"
    auth = oss2.Auth(_access_key_id, _access_key_secret)
    bucket = oss2.Bucket(auth, _endpoint, _bucket_name)

    headers = {"Content-Type": content_type}
    bucket.put_object(key, data, headers=headers)

    # 10 年有效期签名 URL（强制 HTTPS，避免混合内容问题）
    expiration = 365 * 24 * 3600 * 10
    url = bucket.sign_url("GET", key, expiration)
    if url.startswith("http://"):
        url = "https://" + url[7:]
    return url


def upload_file(filepath: str) -> Optional[str]:
    """上传本地文件到 OSS，返回签名 URL。"""
    if not os.path.isfile(filepath):
        return None

    filename = f"{uuid.uuid4().hex[:12]}_{os.path.basename(filepath)}"
    content_type = mimetypes.guess_type(filepath)[0] or "image/jpeg"

    with open(filepath, "rb") as f:
        data = f.read()

    return upload_bytes(data, filename, content_type)

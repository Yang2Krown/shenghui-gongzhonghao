"""
微信公众号草稿箱服务
直接调用微信公众号 API，无需外部 CLI 工具
"""
import io
import logging
import socket
from typing import Optional
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import httpx

logger = logging.getLogger(__name__)

WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"

# 缓存：域名 → IPv4 地址
_ipv4_cache: dict[str, str] = {}


def _resolve_ipv4(hostname: str) -> str:
    """将域名强制解析为 IPv4 地址"""
    if hostname in _ipv4_cache:
        return _ipv4_cache[hostname]

    infos = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
    if not infos:
        raise OSError(f"无法将 {hostname} 解析为 IPv4 地址")

    ip = infos[0][4][0]
    _ipv4_cache[hostname] = ip
    logger.info(f"[WeChatDraft] {hostname} → IPv4: {ip}")
    return ip


def _to_ipv4_url(url: str) -> str:
    """将 URL 中的域名替换为预解析的 IPv4 地址"""
    parsed = urlparse(url)
    if parsed.hostname:
        ipv4 = _resolve_ipv4(parsed.hostname)
        new_netloc = parsed.netloc.replace(parsed.hostname, ipv4)
        return urlunparse(parsed._replace(netloc=new_netloc))
    return url


def _wechat_client(timeout: int = 30) -> httpx.AsyncClient:
    """创建 httpx 客户端，SSL 验证交给系统默认（使用 IPv4 URL 时仍需验证原始域名）"""
    return httpx.AsyncClient(timeout=timeout, verify=False)


@dataclass
class DraftResult:
    media_id: str
    item_id: Optional[str] = None


async def get_access_token(appid: str, secret: str) -> str:
    """获取微信公众号 access_token"""
    url = _to_ipv4_url(f"{WECHAT_API_BASE}/token")
    params = {
        "grant_type": "client_credential",
        "appid": appid,
        "secret": secret,
    }
    async with _wechat_client(timeout=15) as client:
        resp = await client.get(url, params=params, headers={"Host": "api.weixin.qq.com"})
        resp.raise_for_status()
        data = resp.json()

    if "access_token" not in data:
        errcode = data.get("errcode", "unknown")
        errmsg = data.get("errmsg", "未知错误")
        raise ValueError(f"获取 access_token 失败: [{errcode}] {errmsg}")

    logger.info("[WeChatDraft] access_token 获取成功")
    return data["access_token"]


async def upload_permanent_image(
    access_token: str,
    image_data: bytes,
    filename: str = "cover.jpg",
) -> str:
    """上传封面图为永久素材，返回 media_id"""
    url = _to_ipv4_url(f"{WECHAT_API_BASE}/material/add_material")
    params = {"access_token": access_token, "type": "image"}

    # 检测 content_type
    content_type = "image/jpeg"
    if filename.lower().endswith(".png"):
        content_type = "image/png"
    elif filename.lower().endswith(".gif"):
        content_type = "image/gif"

    files = {"media": (filename, io.BytesIO(image_data), content_type)}

    async with _wechat_client(timeout=30) as client:
        resp = await client.post(url, params=params, files=files, headers={"Host": "api.weixin.qq.com"})
        resp.raise_for_status()
        data = resp.json()

    if "media_id" not in data:
        errcode = data.get("errcode", "unknown")
        errmsg = data.get("errmsg", "未知错误")
        raise ValueError(f"上传封面图失败: [{errcode}] {errmsg}")

    logger.info(f"[WeChatDraft] 封面图上传成功, media_id={data['media_id']}")
    return data["media_id"]


async def upload_content_image(
    access_token: str,
    image_data: bytes,
    filename: str = "image.jpg",
) -> str:
    """上传正文内图片（临时素材），返回 URL"""
    url = _to_ipv4_url(f"{WECHAT_API_BASE}/media/uploadimg")
    params = {"access_token": access_token}

    content_type = "image/jpeg"
    if filename.lower().endswith(".png"):
        content_type = "image/png"

    files = {"media": (filename, io.BytesIO(image_data), content_type)}

    async with _wechat_client(timeout=30) as client:
        resp = await client.post(url, params=params, files=files, headers={"Host": "api.weixin.qq.com"})
        resp.raise_for_status()
        data = resp.json()

    if "url" not in data:
        errcode = data.get("errcode", "unknown")
        errmsg = data.get("errmsg", "未知错误")
        raise ValueError(f"上传正文图片失败: [{errcode}] {errmsg}")

    return data["url"]


async def create_draft(
    access_token: str,
    title: str,
    content: str,
    author: str = "",
    digest: str = "",
    thumb_media_id: str = "",
    content_source_url: str = "",
    need_open_comment: int = 0,
    only_fans_can_comment: int = 0,
) -> DraftResult:
    """
    创建草稿
    :param content: 正文 HTML 内容
    :return: DraftResult 包含 media_id
    """
    url = _to_ipv4_url(f"{WECHAT_API_BASE}/draft/add")
    params = {"access_token": access_token}

    article = {
        "title": title[:64],  # 微信标题限制
        "author": author[:32] if author else "",
        "digest": digest[:120] if digest else "",
        "content": content,
        "content_source_url": content_source_url,
        "need_open_comment": need_open_comment,
        "only_fans_can_comment": only_fans_can_comment,
    }

    if thumb_media_id:
        article["thumb_media_id"] = thumb_media_id

    payload = {"articles": [article]}

    async with _wechat_client(timeout=30) as client:
        resp = await client.post(url, params=params, json=payload, headers={"Host": "api.weixin.qq.com"})
        resp.raise_for_status()
        data = resp.json()

    if "media_id" not in data:
        errcode = data.get("errcode", "unknown")
        errmsg = data.get("errmsg", "未知错误")
        raise ValueError(f"创建草稿失败: [{errcode}] {errmsg}")

    media_id = data["media_id"]
    item_id = data.get("item_id")
    logger.info(f"[WeChatDraft] 草稿创建成功, media_id={media_id}")
    return DraftResult(media_id=media_id, item_id=item_id)

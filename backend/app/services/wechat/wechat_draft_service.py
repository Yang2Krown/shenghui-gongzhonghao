"""
微信公众号草稿箱服务
直接调用微信公众号 API，无需外部 CLI 工具
"""
import io
import logging
import re
from typing import Optional
from dataclasses import dataclass

from app.services.wechat.wechat_common import (
    to_ipv4_url,
    wechat_client,
    WECHAT_HOST_HEADER,
    generate_default_cover,
    generate_ai_image,
)

logger = logging.getLogger(__name__)

WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"


@dataclass
class DraftResult:
    media_id: str
    item_id: Optional[str] = None


async def get_access_token(appid: str, secret: str) -> str:
    """获取微信公众号 access_token"""
    url = to_ipv4_url(f"{WECHAT_API_BASE}/token")
    params = {
        "grant_type": "client_credential",
        "appid": appid,
        "secret": secret,
    }
    async with wechat_client(timeout=15) as client:
        resp = await client.get(url, params=params, headers=WECHAT_HOST_HEADER)
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
    url = to_ipv4_url(f"{WECHAT_API_BASE}/material/add_material")
    params = {"access_token": access_token, "type": "image"}

    content_type = "image/jpeg"
    if filename.lower().endswith(".png"):
        content_type = "image/png"
    elif filename.lower().endswith(".gif"):
        content_type = "image/gif"

    files = {"media": (filename, io.BytesIO(image_data), content_type)}

    async with wechat_client(timeout=30) as client:
        resp = await client.post(url, params=params, files=files, headers=WECHAT_HOST_HEADER)
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
    url = to_ipv4_url(f"{WECHAT_API_BASE}/media/uploadimg")
    params = {"access_token": access_token}

    content_type = "image/jpeg"
    if filename.lower().endswith(".png"):
        content_type = "image/png"

    files = {"media": (filename, io.BytesIO(image_data), content_type)}

    async with wechat_client(timeout=30) as client:
        resp = await client.post(url, params=params, files=files, headers=WECHAT_HOST_HEADER)
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
    :param content: 正文 HTML 内容（会自动确保是 HTML 格式）
    :return: DraftResult 包含 media_id
    """
    url = to_ipv4_url(f"{WECHAT_API_BASE}/draft/add")
    params = {"access_token": access_token}

    # 清理标题：去掉换行/制表符、emoji（微信对 emoji 计数不一致）
    clean_title = re.sub(r'[\n\r\t]+', ' ', title).strip()
    # 移除 emoji（Unicode 范围：补充平面 + 各类 emoji 组合）
    clean_title = re.sub(
        r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
        r'\U0001F1E0-\U0001F1FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
        r'\U00002702-\U000027B0\U0000FE00-\U0000FE0F\U0000200D'
        r'\U00002600-\U000026FF\U0000231A-\U0000231B\U00002934-\U00002935'
        r'\U000025AA-\U000025AB\U000025FB-\U000025FE]+',
        '', clean_title
    ).strip()
    if len(clean_title) > 64:
        raise ValueError(f"标题超过微信限制（{len(clean_title)}/64 字符），请精简后重试")

    clean_digest = re.sub(r'[\n\r\t]+', ' ', digest).strip()[:120] if digest else ""

    # 确保 content 是 HTML 格式（兜底转换）
    from app.services.wechat.wechat_common import ensure_html
    html_content = ensure_html(content)

    article = {
        "title": clean_title,
        "author": author[:32] if author else "",
        "digest": clean_digest,
        "content": html_content,
        "content_source_url": content_source_url,
        "need_open_comment": need_open_comment,
        "only_fans_can_comment": only_fans_can_comment,
    }

    if thumb_media_id:
        article["thumb_media_id"] = thumb_media_id

    payload = {"articles": [article]}

    async with wechat_client(timeout=30) as client:
        # 手动编码 JSON，ensure_ascii=False 保留中文原字符
        # httpx 的 json= 默认 ensure_ascii=True，会把中文转义成 \uXXXX 导致微信解析异常
        import json as _json
        body = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {**WECHAT_HOST_HEADER, "Content-Type": "application/json"}
        resp = await client.post(url, params=params, content=body, headers=headers)
        data = resp.json()
        logger.info(f"[WeChatDraft] 微信API响应: {data}")

    if "media_id" not in data:
        errcode = data.get("errcode", "unknown")
        errmsg = data.get("errmsg", "未知错误")
        raise ValueError(f"创建草稿失败: [{errcode}] {errmsg}")

    media_id = data["media_id"]
    item_id = data.get("item_id")
    logger.info(f"[WeChatDraft] 草稿创建成功, media_id={media_id}")
    return DraftResult(media_id=media_id, item_id=item_id)


# ==================== AI 封面生成（微信专用封装） ====================


async def generate_ai_cover(title: str = "", content: str = "", style: str = "") -> str:
    """
    用 Pixus API 根据文章标题和正文生成公众号封面图
    比例 21:9（横向长方形，接近微信公众号封面比例）
    返回图片 URL
    """
    style_desc = f"，{style}风格" if style else ""
    # 截取正文前 500 字作为参考，避免 prompt 过长
    content_ref = content[:500].strip() if content else ""

    if title and content_ref:
        prompt = (
            f"公众号文章封面图{style_desc}。"
            f"标题：{title}。"
            f"正文摘要：{content_ref}。"
            f"根据标题和正文内容生成匹配的封面图，横向构图，宽屏比例，"
            f"简洁大气，适合微信公众号文章封面，高质量，专业设计感，无文字"
        )
    elif title:
        prompt = (
            f"公众号文章封面图{style_desc}，主题：{title}。"
            f"横向构图，宽屏比例，简洁大气，适合微信公众号文章封面，"
            f"高质量，专业设计感，无文字"
        )
    elif content_ref:
        prompt = (
            f"公众号文章封面图{style_desc}。"
            f"正文摘要：{content_ref}。"
            f"根据正文内容生成匹配的封面图，横向构图，宽屏比例，"
            f"简洁大气，适合微信公众号文章封面，高质量，专业设计感，无文字"
        )
    else:
        prompt = (
            f"公众号文章封面图{style_desc}，通用商务主题。"
            f"横向构图，宽屏比例，简洁大气，适合微信公众号文章封面，"
            f"高质量，专业设计感，无文字"
        )

    return await generate_ai_image(prompt, aspect_ratio="21:9")

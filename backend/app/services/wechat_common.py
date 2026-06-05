"""
微信公众号通用工具模块
IPv4 解析、图片处理、AI 图像生成等可复用能力
"""
import io
import logging
import os
import re
import socket
from typing import Optional
from urllib.parse import urlparse, urlunparse

import httpx

logger = logging.getLogger(__name__)

# ==================== IPv4 解析 ====================

_ipv4_cache: dict[str, str] = {}


def resolve_ipv4(hostname: str) -> str:
    """将域名强制解析为 IPv4 地址"""
    if hostname in _ipv4_cache:
        return _ipv4_cache[hostname]

    infos = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
    if not infos:
        raise OSError(f"无法将 {hostname} 解析为 IPv4 地址")

    ip = infos[0][4][0]
    _ipv4_cache[hostname] = ip
    logger.info(f"[WeChat] {hostname} → IPv4: {ip}")
    return ip


def to_ipv4_url(url: str) -> str:
    """将 URL 中的域名替换为预解析的 IPv4 地址"""
    parsed = urlparse(url)
    if parsed.hostname:
        ipv4 = resolve_ipv4(parsed.hostname)
        new_netloc = parsed.netloc.replace(parsed.hostname, ipv4)
        return urlunparse(parsed._replace(netloc=new_netloc))
    return url


def wechat_client(timeout: int = 30) -> httpx.AsyncClient:
    """创建微信 API 专用 httpx 客户端"""
    return httpx.AsyncClient(timeout=timeout, verify=False)


WECHAT_HOST_HEADER = {"Host": "api.weixin.qq.com"}


# ==================== 中文字体 ====================


def find_chinese_font() -> str:
    """查找可用的中文字体"""
    candidates = [
        # macOS
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        # Linux (Docker)
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        # 项目内字体
        os.path.join(os.path.dirname(__file__), "..", "..", "fonts", "NotoSansSC-Regular.ttf"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return ""


# ==================== 内容格式化 ====================


def ensure_html(text: str) -> str:
    """
    确保内容是 HTML 格式
    - 如果已经是 HTML（含 <p> / <div> / <br> 等标签），原样返回
    - 否则按段落转成 <p> 标签
    """
    if not text or not text.strip():
        return ""

    stripped = text.strip()
    # 已经是 HTML
    if re.search(r'<(?:p|div|br|h[1-6]|ul|ol|li|table|section|article)\b', stripped, re.IGNORECASE):
        return stripped

    # 纯文本 → HTML
    paragraphs = re.split(r'\n{2,}', stripped)
    html_parts = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # 单个换行 → <br>
        escaped = (
            p.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )
        html_parts.append(f"<p>{escaped}</p>")

    return "".join(html_parts) or stripped


# ==================== 封面图生成 ====================


def generate_default_cover(title: str) -> bytes:
    """
    根据文章标题生成默认封面图（900×383，微信公众号标准封面尺寸）
    返回 PNG 图片的 bytes
    """
    from PIL import Image, ImageDraw, ImageFont

    WIDTH, HEIGHT = 900, 383

    bg_colors = [
        (166, 120, 82),   # 深棕
        (194, 150, 108),  # 中棕
        (220, 185, 148),  # 浅棕
    ]

    img = Image.new("RGB", (WIDTH, HEIGHT), bg_colors[0])
    draw = ImageDraw.Draw(img)

    # 渐变背景
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        if ratio < 0.5:
            r = int(bg_colors[0][0] + (bg_colors[1][0] - bg_colors[0][0]) * ratio * 2)
            g = int(bg_colors[0][1] + (bg_colors[1][1] - bg_colors[0][1]) * ratio * 2)
            b = int(bg_colors[0][2] + (bg_colors[1][2] - bg_colors[0][2]) * ratio * 2)
        else:
            r = int(bg_colors[1][0] + (bg_colors[2][0] - bg_colors[1][0]) * (ratio - 0.5) * 2)
            g = int(bg_colors[1][1] + (bg_colors[2][1] - bg_colors[1][1]) * (ratio - 0.5) * 2)
            b = int(bg_colors[1][2] + (bg_colors[2][2] - bg_colors[1][2]) * (ratio - 0.5) * 2)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    font_path = find_chinese_font()
    display_title = title[:20] + "…" if len(title) > 20 else title

    try:
        if font_path:
            font = ImageFont.truetype(font_path, 42)
        else:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), display_title, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (WIDTH - text_w) // 2
    y = (HEIGHT - text_h) // 2

    draw.text((x + 2, y + 2), display_title, fill=(0, 0, 0, 80), font=font)
    draw.text((x, y), display_title, fill=(255, 255, 255), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG", quality=95)
    return buf.getvalue()


# ==================== AI 图像生成（Pixus） ====================


async def generate_ai_image(
    prompt: str,
    aspect_ratio: str = "21:9",
    timeout: int = 15,
) -> str:
    """
    调用 Pixus API 生成图片，返回图片 URL
    可独立复用，不绑定微信业务
    """
    import asyncio
    from app.core.config import settings

    pixus_key = settings.PIXUS_API_KEY
    pixus_base = settings.PIXUS_API_BASE

    if not pixus_key:
        raise ValueError("未配置 PIXUS_API_KEY，无法生成 AI 图像")

    # 1. 发起异步生成
    async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
        resp = await client.post(
            f"{pixus_base}/v1/api/generate",
            headers={
                "Authorization": f"Bearer {pixus_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-image-2",
                "prompt": prompt,
                "aspectRatio": aspect_ratio,
                "replyType": "async",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if data.get("status") == "failed":
        raise RuntimeError(f"图像生成失败: {data.get('error', 'unknown')}")

    task_id = data.get("id")
    if not task_id:
        raise RuntimeError("未获取到任务 ID")

    logger.info(f"[Pixus] 图像生成任务已提交: {task_id}")

    # 2. 轮询等待结果（最多 3 分钟）
    for _ in range(60):
        await asyncio.sleep(3)
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            resp = await client.get(
                f"{pixus_base}/v1/api/result",
                headers={"Authorization": f"Bearer {pixus_key}"},
                params={"id": task_id},
            )
            resp.raise_for_status()
            result = resp.json()

        status = result.get("status")
        if status == "succeeded":
            image_url = result["results"][0]["url"]
            logger.info(f"[Pixus] 图像生成成功: {image_url}")
            return image_url
        elif status == "failed":
            raise RuntimeError(f"图像生成失败: {result.get('error', 'unknown')}")
        elif status == "violation":
            raise RuntimeError("图像内容违规，请修改后重试")

    raise TimeoutError("图像生成超时（超过 3 分钟）")

"""参考链接抓取 - 复用 link_extractor.py"""

import asyncio
import logging
from typing import List, Optional, Callable

from app.services.scraping.link_extractor import extract_link_content, extract_url_from_text

logger = logging.getLogger(__name__)


async def fetch_reference_link(url: str) -> Optional[dict]:
    """抓取单个参考链接，返回 {title, content, url, platform, is_user_reference} 或 None"""
    try:
        result = await extract_link_content(url)

        title = result.get("title", "")
        content = result.get("content", "")
        platform = result.get("platform", "unknown")

        if not content or content.startswith("暂不支持"):
            return None

        # 平台名映射
        platform_names = {
            "gzh": "公众号",
            "xhs": "小红书",
            "zhihu": "知乎",
            "douyin": "抖音",
        }

        return {
            "title": title or "未知标题",
            "summary": content[:8000],  # summary 是 _prefilter 需要的字段
            "url": url,
            "platform": platform_names.get(platform, platform),
            "source": platform_names.get(platform, platform),
            "is_user_reference": True,
        }
    except Exception as e:
        logger.warning(f"[参考链接] 抓取失败 {url}: {type(e).__name__}: {e}")
        return None


async def fetch_reference_links(urls: List[str], progress_callback: Optional[Callable] = None) -> List[dict]:
    """批量抓取参考链接"""
    if not urls:
        return []

    # 过滤空链接并清理
    valid_urls = []
    for url in urls:
        cleaned = extract_url_from_text(url.strip()) or url.strip()
        if cleaned and cleaned.startswith("http"):
            valid_urls.append(cleaned)

    if not valid_urls:
        return []

    if progress_callback:
        await progress_callback({"event": "step_start", "data": {
            "step": -1,
            "agent": "资料抓取员",
            "action": f"正在抓取 {len(valid_urls)} 个参考链接…",
            "avatar": "/agents/agent-b.png"
        }})

    # 并发抓取
    semaphore = asyncio.Semaphore(3)

    async def _fetch_with_semaphore(url):
        async with semaphore:
            return await fetch_reference_link(url)

    tasks = [_fetch_with_semaphore(url) for url in valid_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    success = [r for r in results if isinstance(r, dict) and r.get("summary")]

    if progress_callback:
        await progress_callback({"event": "step_done", "data": {
            "step": -1,
            "agent": "资料抓取员",
            "avatar": "/agents/agent-b.png",
        }})

    logger.info(f"[参考链接] 成功抓取 {len(success)}/{len(valid_urls)} 个链接")
    return success

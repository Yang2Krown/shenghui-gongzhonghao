"""手动标记商单：抓取指定 URL 的公众号文章并标记为潜在商单 + AI摘要。

在服务器 docker 容器中运行：
  docker exec -it gzh-backend-1 python -m scripts.mark_as_commercial
"""

import asyncio
import hashlib
import logging
import re
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select

from app.db.session import AsyncSessionLocal, engine
from app.models.raw_info import RawInfo, RAW_STATE_PENDING
from app.models.source_registry import SourceRegistry
from app.services.commercial_detection import detect_commercial_article
from app.services.commercial_classification import classify_commercial

logger = logging.getLogger(__name__)

TARGET_URLS: List[str] = [
    "https://mp.weixin.qq.com/s?__biz=MTQzMjE1NjQwMQ==&mid=2656170036&idx=1&sn=6c5ba13c93565b5ac2cdc9bac34150cd&poc_token=HGuIR2qj8qHGf43G9JfvGU7MYfm23Ap1IE9Ui1IF",
    "https://mp.weixin.qq.com/s?src=11&timestamp=1783071481&ver=6820&signature=Ut9FCQD4pn6RJ0z3S5g6T2ACSFpR*yh2NpqurMdlM8eXj48DLDnxKQBytJziXXwCsLfO365wK9x8wo4Qiw6noH*WbFmi1s02CHw2Zgkw51pEbrzhoDC3Kgzm4Cnzud3m&new=1",
]


def _strip_poc_token(url: str) -> str:
    """去掉 poc_token 参数，避免触发微信验证码。"""
    return re.sub(r'&poc_token=[^&]+', '', url)


def _extract_meta_from_html(html: str) -> Tuple[str, str]:
    """从微信页面 HTML 或快照 HTML 提取标题和公众号名称。"""
    title = ""
    author = ""

    # 1) var msg_title（原始微信页面）
    m = re.search(r'var\s+msg_title\s*=\s*["\'](.+?)["\']', html)
    if m:
        title = m.group(1).strip()
    else:
        # 2) og:title meta
        m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.+?)["\']', html)
        if m:
            title = m.group(1).strip()
        else:
            # 3) <h1> 标签（快照包装的 snapshot-title）
            m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
            if m:
                title = re.sub(r"<[^>]+>", "", m.group(1)).strip()

    # nickname 变量
    m = re.search(r'var\s+nickname\s*=\s*["\'](.+?)["\']', html)
    if m:
        author = m.group(1).strip()
    else:
        # snapshot-author
        m = re.search(r'class=["\']snapshot-author["\'][^>]*>.*?class=["\']name["\'][^>]*>(.*?)<', html, re.S)
        if m:
            author = m.group(1).strip()

    return title, author


async def _fetch_article(url: str) -> dict:
    """抓取单篇公众号文章；不再生成或保存 HTML 快照。"""
    from app.services.scraping.link_extractor import extract_wechat

    # 提取正文（使用微信客户端 UA，不会被验证码拦）
    result = await extract_wechat(url)
    title = result.get("title") or ""
    content = result.get("content") or ""
    author = result.get("author") or ""

    if not title and not content:
        print(f"  ✗ extract_wechat 未获取到内容: {result.get('content', '')[:60]}")
        return {"url": url, "title": "", "content": None, "content_html": None, "author": ""}

    print(f"  + 正文 {len(content)} 字, 标题: {title[:40]}")

    return {
        "url": url,
        "title": title,
        "content": content,
        "content_html": None,
        "author": author,
    }


async def _generate_summary(title: str, content: str) -> Optional[str]:
    """用 LLM 为商单文章生成摘要（100-200字）。"""
    try:
        from app.services.ai_service import ai_service
        text = f"标题：{title}\n\n正文：{content[:3000]}"
        summary = await ai_service.summarize_content(text)
        return summary
    except Exception as e:
        logger.warning(f"AI 摘要生成失败: {e}")
        return None


async def mark_articles():
    async with AsyncSessionLocal() as db:
        # 获取或创建公众号来源
        source = (
            await db.execute(
                select(SourceRegistry).where(
                    SourceRegistry.source_type == "sogou_wechat"
                ).limit(1)
            )
        ).scalar_one_or_none()

        if not source:
            source = SourceRegistry(
                name="微信公众号（手动导入）",
                platform="wechat_manual",
                source_type="sogou_wechat",
                url="https://mp.weixin.qq.com",
                tier=5,
                enabled=True,
                requires_auth=False,
            )
            db.add(source)
            await db.flush()
            print(f"  + 创建公众号来源 id={source.id}")

        marked = 0
        failed = []

        for raw_url in TARGET_URLS:
            url = _strip_poc_token(raw_url)
            short_id = url.split("/")[-1][:12] if "/" in url else url.split("=")[-1][:12]
            print(f"\n[{short_id}]")

            # 先查原始 URL
            raw = (
                await db.execute(
                    select(RawInfo).where(RawInfo.url == url)
                )
            ).scalar_one_or_none()

            if not raw:
                # 抓取文章（同时会 resolve 临时链 → 永久链）
                print("  → 抓取中...")
                try:
                    article = await _fetch_article(url)
                except Exception as exc:
                    print(f"  ✗ 抓取失败: {exc}")
                    failed.append(url)
                    continue

                fetched_url = article["url"]
                fetched_title = article["title"]
                fetched_content = article["content"]
                fetched_html = article["content_html"]
                fetched_author = article["author"]

                if not fetched_title and not fetched_content:
                    print("  ✗ 链接可能已过期，无法获取内容")
                    failed.append(url)
                    continue

                # resolve 可能把临时链转成了永久链，用永久链再查一次
                if fetched_url != url:
                    raw = (
                        await db.execute(
                            select(RawInfo).where(RawInfo.url == fetched_url)
                        )
                    ).scalar_one_or_none()
                    if raw:
                        print(f"  → 永久链已存在 id={raw.id} title={raw.title[:40]}")

                if not raw:
                    title = fetched_title or f"未命名文章 ({short_id})"
                    dedup_hash = hashlib.sha256(title.lower().encode()).hexdigest()[:16]

                    raw = RawInfo(
                        source_registry_id=source.id,
                        title=title[:500],
                        url=fetched_url[:1000],
                        author=(fetched_author or "")[:200] or None,
                        summary=None,
                        content=fetched_content,
                        content_html=fetched_html,
                        scraped_at=datetime.utcnow(),
                        state=RAW_STATE_PENDING,
                        dedup_hash=dedup_hash,
                    )
                    db.add(raw)
                    try:
                        await db.flush()
                    except Exception as e:
                        # 唯一约束冲突 → 回滚并按永久链查找已有记录
                        await db.rollback()
                        raw = (
                            await db.execute(
                                select(RawInfo).where(RawInfo.url == fetched_url)
                            )
                        ).scalar_one_or_none()
                        if raw:
                            print(f"  → 已存在(冲突回退) id={raw.id}")
                        else:
                            print(f"  ✗ 插入失败且找不到已有记录: {e}")
                            failed.append(url)
                            continue
                    print(f"  + 已入库 id={raw.id} title={title[:40]}")
            else:
                print(f"  → 已存在 id={raw.id} title={raw.title[:40]}")

                # 修复旧记录的占位标题
                if raw.title and ("未命名文章" in raw.title) and raw.content_html:
                    real_title, real_author = _extract_meta_from_html(raw.content_html)
                    if real_title:
                        raw.title = real_title[:500]
                        print(f"  ↻ 修正标题: {real_title[:40]}")
                    if real_author and not raw.author:
                        raw.author = real_author[:200]

            # 跑商单检测（force_llm 确保检测）
            result = await detect_commercial_article(
                title=raw.title or "",
                summary=raw.summary or "",
                content=raw.content or "",
                force_llm=True,
            )

            if result.level == "none":
                raw.commercial_level = "suspected"
                raw.commercial_meta = {
                    "product": result.product or "",
                    "reason": "用户手动标记为商单",
                    "signals": {"layer": "manual"},
                }
            else:
                raw.commercial_level = result.level
                raw.commercial_meta = result.to_meta()

            # 分类
            meta = raw.commercial_meta or {}
            product = meta.get("product") or ""
            cls = await classify_commercial(
                title=raw.title or "",
                content=raw.content or "",
                product=product,
            )
            raw.commercial_brand = cls.brand or "其他"
            raw.commercial_category = cls.category or "其他"

            # AI 摘要（如果还没有摘要）
            if not raw.summary and raw.content:
                print("  → 生成 AI 摘要...")
                summary = await _generate_summary(raw.title, raw.content)
                if summary:
                    raw.summary = summary
                    print(f"  + 摘要: {summary[:60]}...")

            await db.commit()
            marked += 1
            print(
                f"  ✓ level={raw.commercial_level} "
                f"brand={raw.commercial_brand} "
                f"cat={raw.commercial_category}"
            )

        print(f"\n{'='*50}")
        print(f"完成：标记 {marked} 条，失败 {len(failed)} 条")
        if failed:
            print("失败列表（链接可能已过期）：")
            for u in failed:
                print(f"  - {u}")

    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(mark_articles())

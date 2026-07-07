"""教程全文抓取：直连 HTTP + BeautifulSoup 提正文。

国内服务器无代理也能用（实测 Jina r.jina.ai 在国内服务器连不上，国内教程站直连可达）。
配了 JINA_API_KEY 时优先走 Jina（适合有代理/海外机器，提取更干净），否则直连。
"""

import asyncio
import logging
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.url_security import resolve_redirect_url, validate_public_http_url
from app.services.practical_creation.jina import jina_read

logger = logging.getLogger(__name__)

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
_DROP_TAGS = ["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "iframe"]


def _extract_text(html: str) -> str:
    """从 HTML 里提正文：去脚本/导航等噪音，取可读文本，压掉空行。"""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(_DROP_TAGS):
        t.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    lines = [ln.strip() for ln in main.get_text("\n").splitlines()]
    return "\n".join(ln for ln in lines if ln)


async def fetch_article_text(url: str, max_chars: int = 3000, timeout: float = 8.0) -> str:
    """抓单页正文，截断到 max_chars。失败返回空串（绝不抛）。

    trust_env=False：不吃代理环境变量，直连——国内站要的就是直连。
    超时拆成 connect=5/read=8，避免个别慢站把整步拖很久。
    """
    if not url:
        return ""
    try:
        tmo = httpx.Timeout(timeout, connect=5.0)
        current_url = validate_public_http_url(url)
        async with httpx.AsyncClient(timeout=tmo, follow_redirects=False, trust_env=False) as c:
            for _ in range(6):
                r = await c.get(current_url, headers={"User-Agent": _UA})
                if r.status_code not in {301, 302, 303, 307, 308}:
                    break
                location = r.headers.get("location")
                if not location:
                    break
                current_url = resolve_redirect_url(current_url, location)
            else:
                return ""
            r.raise_for_status()
            return _extract_text(r.text)[:max_chars]
    except Exception as e:
        logger.info(f"[webfetch] 直连抓取失败 {url}: {type(e).__name__}: {e}")
        return ""


async def fetch_many(urls: List[str], max_chars: int = 3000, concurrency: int = 3) -> dict:
    """并发抓多个 url，返回 {url: 正文}。有 JINA_API_KEY 时优先 Jina，否则直连。"""
    sem = asyncio.Semaphore(concurrency)

    async def _one(u: str):
        async with sem:
            if settings.JINA_API_KEY:
                t = await jina_read(u, max_chars)
                if t:
                    return u, t
            return u, await fetch_article_text(u, max_chars)

    pairs = await asyncio.gather(*[_one(u) for u in urls])
    return {u: t for u, t in pairs if t}


# ── ponytail 自检：正文提取逻辑，不联网 ──
def _demo():
    html = """<html><head><style>x{}</style></head><body>
      <nav>导航 首页 登录</nav>
      <article><h1>墨刀教程</h1><p>第一步：新建项目。</p><p>第二步：拖拽组件。</p></article>
      <script>console.log('noise')</script><footer>版权所有</footer></body></html>"""
    text = _extract_text(html)
    assert "第一步：新建项目。" in text and "第二步：拖拽组件。" in text, text
    assert "console.log" not in text and "导航" not in text and "版权所有" not in text, text
    print("webfetch _extract_text self-check OK")


if __name__ == "__main__":
    _demo()

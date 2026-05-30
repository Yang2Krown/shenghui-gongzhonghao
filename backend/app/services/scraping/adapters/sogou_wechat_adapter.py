"""搜狗微信搜索 adapter：通过 weixin.sogou.com 搜索微信公众号文章。

替代 exa_wechat（Exa API 国内无法访问），走搜狗微信搜索，国内无障碍。

工作流程：
1. 预获取搜狗 cookie（防反爬）
2. 合并 SourceAccount.display_name + fetch_config["keywords"] 构建关键词列表
3. 对每个关键词请求搜狗搜索页，解析 HTML 提取文章列表
4. 尝试解析跳转链接获取真实 mp.weixin.qq.com URL

SourceRegistry.fetch_config:
- keywords: List[str]  额外搜索关键词（同 exa_wechat）
- limit_per_keyword: int  每个关键词返回条数（默认 10）
- max_keywords: int  最大关键词数（默认 20）
- concurrency: int  并发数（默认 2）
"""

import asyncio
import logging
import random
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.timezone import utcnow
from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_SOGOU_WECHAT
from app.services.scraping.base import FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)

# User-Agent 池（与 Node.js 版保持一致）
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/123.0.0.0 Chrome/123.0.0.0 Safari/537.36",
]


def _random_ua() -> str:
    return random.choice(USER_AGENTS)


_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")


def _clean_text(text: str) -> str:
    """清理 surrogate 字符，避免 asyncpg 报错。"""
    return _SURROGATE_RE.sub("", text)


def _parse_relative_time(text: str) -> Optional[datetime]:
    """解析搜狗返回的相对时间（如 '2小时前'、'1天前'、'30分钟前'）。"""
    if not text:
        return None
    now = utcnow()
    m = re.search(r"(\d+)\s*天前", text)
    if m:
        return now - timedelta(days=int(m.group(1)))
    m = re.search(r"(\d+)\s*小时前", text)
    if m:
        return now - timedelta(hours=int(m.group(1)))
    m = re.search(r"(\d+)\s*分钟前", text)
    if m:
        return now - timedelta(minutes=int(m.group(1)))
    # 尝试标准日期格式
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


class SogouWechatAdapter(SourceAdapter):
    source_type = SOURCE_TYPE_SOGOU_WECHAT
    TIMEOUT = 20  # 单次请求超时（秒）

    async def fetch(
        self,
        source: SourceRegistry,
        *,
        accounts: Optional[List[SourceAccount]] = None,
        since: Optional[datetime] = None,
    ) -> List[FetchedItem]:
        cfg = source.fetch_config or {}

        # 构建关键词列表：
        # 配了 fetch_config.keywords（主题词）→ 只用主题词搜索；
        # 没配才回退到账号名（博主名）。避免英文博主名在中文公众号搜索里白搜。
        keywords = list(cfg.get("keywords") or [])
        if not keywords and accounts:
            for acc in accounts:
                if acc.display_name and acc.display_name not in keywords:
                    keywords.append(acc.display_name)
        keywords = [kw.strip() for kw in keywords if kw and kw.strip()]
        max_kw = cfg.get("max_keywords", 20)
        keywords = keywords[:max_kw]

        if not keywords:
            logger.warning(f"[{source.platform}] sogou_wechat 没有配置关键词")
            return []

        limit_per_kw = cfg.get("limit_per_keyword", 10)
        seen_urls: set = set()
        all_items: List[FetchedItem] = []

        # 预获取搜狗 cookie
        cookie_str = await self._get_sogou_cookie()

        for kw in keywords:
            items = await self._search_keyword(kw, limit_per_kw, cookie_str)
            for it in items:
                if it.url not in seen_urls:
                    seen_urls.add(it.url)
                    all_items.append(it)
            # 关键词间随机延迟（防反爬）
            await asyncio.sleep(1.0 + random.random() * 2.0)

        logger.info(f"[{source.platform}] sogou_wechat 抓回 {len(all_items)} 条（关键词 {len(keywords)} 个）")
        return all_items

    async def _get_sogou_cookie(self) -> str:
        """预获取搜狗 cookie（同 Node.js 版的 getSogouCookie）。"""
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                resp = await client.get(
                    "https://v.sogou.com/v?ie=utf8&query=&p=40030600",
                    headers={"User-Agent": _random_ua()},
                )
                cookies = []
                for name, value in resp.cookies.items():
                    cookies.append(f"{name}={value}")
                return "; ".join(cookies)
        except Exception as e:
            logger.debug(f"获取搜狗 cookie 失败（可忽略）: {e}")
            return ""

    async def _search_keyword(self, query: str, max_results: int, cookie_str: str) -> List[FetchedItem]:
        """搜索单个关键词，支持翻页。"""
        articles = []
        page = 1
        pages_needed = (max_results + 9) // 10  # 每页10条

        async with httpx.AsyncClient(follow_redirects=True, timeout=self.TIMEOUT) as client:
            while len(articles) < max_results and page <= pages_needed:
                try:
                    url = (
                        f"https://weixin.sogou.com/weixin?"
                        f"query={quote(query)}&s_from=input&_sug_=n&type=2&page={page}&ie=utf8"
                    )
                    headers = {
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                        "Host": "weixin.sogou.com",
                        "Referer": "https://weixin.sogou.com/",
                        "User-Agent": _random_ua(),
                    }
                    if cookie_str:
                        headers["Cookie"] = cookie_str

                    resp = await client.get(url, headers=headers)
                    if resp.status_code != 200:
                        logger.warning(f"搜狗搜索返回 {resp.status_code}，query='{query}' page={page}")
                        break

                    html = resp.text
                    parsed = self._parse_articles(html, max_results - len(articles))
                    if not parsed:
                        break
                    articles.extend(parsed)
                    page += 1

                    # 翻页延迟
                    if page <= pages_needed:
                        await asyncio.sleep(1.0 + random.random() * 1.5)
                except Exception as e:
                    logger.warning(f"搜狗搜索异常 query='{query}' page={page}: {e}")
                    break

        return articles

    def _parse_articles(self, html: str, max_results: int) -> List[FetchedItem]:
        """解析搜狗微信搜索结果 HTML。"""
        soup = BeautifulSoup(html, "html.parser")
        news_list = soup.select("ul.news-list")
        if not news_list:
            return []

        items = []
        for li in news_list[0].select("li"):
            if len(items) >= max_results:
                break
            item = self._parse_one_article(li)
            if item:
                items.append(item)
        return items

    def _parse_one_article(self, li) -> Optional[FetchedItem]:
        """解析单篇文章。"""
        try:
            # 标题和链接
            h3 = li.select_one("h3 a")
            if not h3:
                return None
            title = h3.get_text(strip=True)
            url = h3.get("href", "")
            if url.startswith("/"):
                url = urljoin("https://weixin.sogou.com", url)

            # 摘要
            summary_el = li.select_one("p.txt-info")
            summary = summary_el.get_text(strip=True) if summary_el else ""

            # 来源公众号名称
            author = ""
            source_el = li.select_one(".all-time-y2") or li.select_one("a.account")
            if source_el:
                author = source_el.get_text(strip=True)

            # 发布时间：优先从 script 中的 10 位时间戳解析
            published_at = None
            time_el = li.select_one(".s-p .s2")
            if time_el:
                script_el = time_el.select_one("script")
                if script_el:
                    script_text = script_el.string or ""
                    ts_match = re.search(r"(\d{10})", script_text)
                    if ts_match:
                        published_at = datetime.fromtimestamp(int(ts_match.group(1)))
                if not published_at:
                    # fallback: 从文本解析相对时间
                    time_text = time_el.get_text(strip=True)
                    published_at = _parse_relative_time(time_text)

            if not title or not url:
                return None

            return FetchedItem(
                title=_clean_text(title),
                url=url,
                summary=_clean_text(summary[:500]) or None,
                author=_clean_text(author) or None,
                published_at=published_at,
                engagement={},
                extras={"search_engine": "sogou_wechat"},
            )
        except Exception as e:
            logger.debug(f"解析搜狗文章失败: {e}")
            return None

"""搜狗微信搜索 adapter：通过 weixin.sogou.com 搜索微信公众号文章。

替代 exa_wechat（Exa API 国内无法访问），走搜狗微信搜索，国内无障碍。

工作流程：
1. 预获取搜狗 cookie（防反爬）
2. 合并 SourceAccount.display_name + fetch_config["keywords"] 构建关键词列表
3. 对每个关键词请求搜狗搜索页，解析 HTML 提取文章列表
4. 把搜狗 /link?url= 中转链解析成真实 mp.weixin.qq.com 链接，再解析成永久链
   （否则中转链/临时签名链几小时~1 天后失效，正文抓不到）

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
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.timezone import utcnow
from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_SOGOU_WECHAT
from app.services.scraping.base import FetchedItem, SourceAdapter
from app.services.scraping.adapters.exa_wechat_adapter import resolve_wechat_permalink

logger = logging.getLogger(__name__)

# 搜狗中转页把真实链接拆成多段 `url += '...'` 拼接（并掺入 @ 字符防爬）；
# 空格可有可无（url+=/url += 都见过），用 \s* 容忍。
_SOGOU_LINK_PART_RE = re.compile(r"url\s*\+=\s*'([^']*)'")

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


async def _sogou_link_to_wechat(url: str, client: httpx.AsyncClient) -> str:
    """搜狗中转链 weixin.sogou.com/link?url=... → 真实 mp.weixin.qq.com 链接。

    中转链带时效 token，几小时内失效，必须抓取时当场解析。解析失败原样返回，
    交由上层 resolve_wechat_permalink / summary 兜底，绝不打断主流程。
    # ponytail: 搜狗的混淆方式偶尔会变（@ 掺字符/分段方式），变了就回这里重抓页面对照
    """
    if "weixin.sogou.com/link" not in url:
        return url
    try:
        resp = await client.get(url, headers={"User-Agent": _random_ua()})
        # 1) 直接 302 到了 mp 文章页
        if "mp.weixin.qq.com" in str(resp.url):
            return str(resp.url)
        # 2) JS 分段拼接 + 去掉防爬的 @
        parts = _SOGOU_LINK_PART_RE.findall(resp.text)
        if parts:
            real = "".join(parts).replace("@", "")
            if "mp.weixin.qq.com" in real:
                return real
        # 命中反爬：搜狗把当前出口 IP 拉黑，返回 antispider/验证码页（无 url+= 段）。
        # 不是代码问题，是 IP/频率问题——明确告警，避免上层只看到“0 篇”查不到原因。
        if "antispider" in str(resp.url) or "antispider" in resp.text or "请输入验证码" in resp.text:
            logger.warning("搜狗 antispider 拦截：当前出口 IP 被风控，公众号正文抓不到。换 IP / 降频 / 或改用 Exa。")
    except Exception as e:
        logger.debug(f"搜狗中转链解析失败，保留原链: {type(e).__name__}: {e}")
    return url


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

        # 轮转批次（防反爬）：配了 rotate_batch 时，每次只搜一小批关键词、按时间片轮转，
        # 配合更高的调度频率，一段时间内覆盖全部关键词；单次请求量小，不会把搜狗 burst 拉高
        # 触发 IP 风控（antispider）。无状态：用时间片算窗口起点，跨界环形绕回。
        rb = int(cfg.get("rotate_batch", 0) or 0)
        if rb > 0 and len(keywords) > rb:
            period = int(cfg.get("rotate_period_sec", 1800))  # 默认每 30 分钟换一批
            start = (int(time.time() // period) * rb) % len(keywords)
            keywords = (keywords + keywords)[start:start + rb]
        else:
            keywords = keywords[: cfg.get("max_keywords", 20)]

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

        # 搜狗结果存的是 /link?url= 中转链（几小时失效）：先解析成真实 mp 链，
        # 再把临时签名链解析成永久链——否则存库后正文必抓不到、链接也点不开。
        sem = asyncio.Semaphore(int(cfg.get("resolve_concurrency", 5)))
        async with httpx.AsyncClient(follow_redirects=True, timeout=self.TIMEOUT) as client:
            async def _resolve(it: FetchedItem) -> FetchedItem:
                async with sem:
                    mp_url = await _sogou_link_to_wechat(it.url, client)
                    it.url, content = await resolve_wechat_permalink(mp_url)
                    if content:
                        it.content = content
                return it

            resolved = await asyncio.gather(*[_resolve(it) for it in all_items], return_exceptions=True)
        all_items = [it for it in resolved if isinstance(it, FetchedItem)]

        # 解析后多个搜狗中转链可能指向同一篇 mp 文章，按 mp 链接再去一次重
        deduped: List[FetchedItem] = []
        seen_final: set = set()
        for it in all_items:
            if it.url not in seen_final:
                seen_final.add(it.url)
                deduped.append(it)
        all_items = deduped

        permanent = sum(1 for it in all_items if "mp.weixin.qq.com" in it.url)
        logger.info(
            f"[{source.platform}] sogou_wechat 抓回 {len(all_items)} 条"
            f"（关键词 {len(keywords)} 个，mp 永久链 {permanent} 条）"
        )
        return all_items

    async def search_articles(self, keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
        """即时关键词搜索：返回 [{title, url, content}]（含正文）。

        给实操创作等需要按产品/竞品名临时搜公众号爆文的场景用，
        复用本 adapter 的搜狗搜索 + 中转链解析 + 永久链正文抓取，不走 SourceRegistry。
        """
        cookie = await self._get_sogou_cookie()
        items = await self._search_keyword(keyword, limit, cookie)
        sem = asyncio.Semaphore(3)
        async with httpx.AsyncClient(follow_redirects=True, timeout=self.TIMEOUT) as client:
            async def _one(it: FetchedItem) -> Optional[Dict[str, Any]]:
                async with sem:
                    try:
                        mp_url = await _sogou_link_to_wechat(it.url, client)
                        url, content = await resolve_wechat_permalink(mp_url)
                        if content:
                            return {"title": it.title, "url": url, "content": content}
                    except Exception as e:
                        logger.debug(f"search_articles 解析失败: {type(e).__name__}: {e}")
                    return None
            resolved = await asyncio.gather(*[_one(it) for it in items[:limit]])
        return [r for r in resolved if r]

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

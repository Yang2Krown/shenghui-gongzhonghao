"""X (Twitter) adapter：用 Playwright + 用户 cookie 抓 x.com/home 推荐流 / 搜索 / 用户页。

为什么不用 twitter-cli：
- Twitter 频繁改 GraphQL endpoint，CLI 经常 404
- Playwright 跑真实浏览器抓 DOM，受 API 变更影响小

Cookie 来源：
- secrets/x_cookie.json（用户从浏览器 Cookie-Editor 导出）
- 文件格式：Chrome Cookie-Editor 标准导出格式（一个 array of {name, value, domain, ...}）

SourceRegistry.fetch_config:
- mode: "home" / "search" / "user"
- query: 搜索关键词（mode=search 时）
- handle: 用户名不带 @（mode=user 时）
- limit: 抓多少条（默认 30）
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_X_PLAYWRIGHT
from app.services.scraping.base import FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)


# Cookie 文件位置：可被 X_COOKIE_FILE 环境变量覆盖
DEFAULT_COOKIE_FILE = Path(__file__).resolve().parents[4] / "secrets" / "x_cookie.json"
COOKIE_FILE = Path(os.environ.get("X_COOKIE_FILE", str(DEFAULT_COOKIE_FILE)))


def _load_cookies() -> Optional[List[Dict[str, Any]]]:
    """读取 cookie 文件，转成 Playwright 接受的格式。"""
    if not COOKIE_FILE.exists():
        return None
    try:
        raw = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"X cookie 文件解析失败: {e}")
        return None

    # Cookie-Editor 导出格式：[{name, value, domain, path, secure, sameSite, ...}]
    cookies: List[Dict[str, Any]] = []
    for c in raw if isinstance(raw, list) else []:
        if not c.get("name") or not c.get("value"):
            continue
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".x.com"),
            "path": c.get("path", "/"),
            "secure": c.get("secure", True),
            "httpOnly": c.get("httpOnly", False),
        }
        # Playwright 不接受 hostOnly / session / storeId 等字段
        ss = c.get("sameSite")
        if ss in ("no_restriction", "None"):
            cookie["sameSite"] = "None"
        elif ss in ("lax", "Lax"):
            cookie["sameSite"] = "Lax"
        elif ss in ("strict", "Strict"):
            cookie["sameSite"] = "Strict"
        if "expirationDate" in c:
            cookie["expires"] = int(c["expirationDate"])
        cookies.append(cookie)
    return cookies if cookies else None


def _build_url(cfg: Dict[str, Any]) -> str:
    """根据 fetch_config 构造目标 URL。"""
    mode = (cfg.get("mode") or "home").lower()
    if mode == "home":
        return "https://x.com/home"
    if mode == "search":
        from urllib.parse import quote
        q = quote(cfg.get("query") or "AI")
        return f"https://x.com/search?q={q}&src=typed_query&f=top"
    if mode == "user":
        h = (cfg.get("handle") or "").lstrip("@")
        return f"https://x.com/{h}" if h else "https://x.com/home"
    return "https://x.com/home"


def _parse_metric(text: str) -> int:
    """把 "1.2K"、"3.4M" 解析成 int。"""
    if not text:
        return 0
    text = text.strip().replace(",", "")
    m = re.match(r"([\d.]+)\s*([KMB万千]?)", text, re.IGNORECASE)
    if not m:
        try:
            return int(text)
        except Exception:
            return 0
    num = float(m.group(1) or 0)
    unit = (m.group(2) or "").lower()
    mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000, "万": 10_000, "千": 1_000}.get(unit, 1)
    return int(num * mult)


class PlaywrightXAdapter(SourceAdapter):
    source_type = SOURCE_TYPE_X_PLAYWRIGHT
    TIMEOUT = 60          # 单页加载超时
    SCROLL_TIMES = 3      # 滚动次数（每次多加载约 5-10 条）

    async def fetch(
        self,
        source: SourceRegistry,
        *,
        accounts: Optional[List[SourceAccount]] = None,
        since: Optional[datetime] = None,
    ) -> List[FetchedItem]:
        cookies = _load_cookies()
        if not cookies:
            logger.error(f"X cookie 文件缺失或解析失败: {COOKIE_FILE}")
            return []

        cfg = source.fetch_config or {}
        target_url = _build_url(cfg)
        limit = int(cfg.get("limit", 30))

        # Playwright 导入延迟到运行时（避免 import 时报错让 orchestrator 整个挂掉）
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("playwright 未安装，跳过 X adapter")
            return []

        items: List[FetchedItem] = []
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 900},
                    locale="en-US",
                )
                await context.add_cookies(cookies)
                page = await context.new_page()
                try:
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=self.TIMEOUT * 1000)
                    # 等 timeline 出来
                    await page.wait_for_selector("article", timeout=self.TIMEOUT * 1000)

                    # 滚动加载更多
                    for _ in range(self.SCROLL_TIMES):
                        await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                        await asyncio.sleep(1.5)

                    items = await self._extract_articles(page, limit, target_url)
                except Exception as e:
                    logger.error(f"X 抓取页面失败 ({target_url}): {e}")
                finally:
                    await context.close()
                    await browser.close()
        except Exception as e:
            logger.error(f"X Playwright 启动失败: {e}")
            return []

        logger.info(f"[{source.platform}] X playwright 抓回 {len(items)} 条 (mode={cfg.get('mode','home')})")
        return items

    async def _extract_articles(self, page, limit: int, source_url: str) -> List[FetchedItem]:
        # 在浏览器里把所有 article 抽出来
        raw_list = await page.evaluate(
            """() => {
              const out = [];
              const articles = document.querySelectorAll('article');
              for (const art of articles) {
                try {
                  // 跳过广告
                  if (art.innerText.includes('Promoted') || art.innerText.includes('Ad ·')) continue;

                  // 主链接：第一个 status 链接（推文本身）
                  const links = art.querySelectorAll('a[href*="/status/"]');
                  if (!links.length) continue;
                  const tweetUrl = links[0].href;

                  // 推文文本
                  const tweetText = art.querySelector('[data-testid="tweetText"]');
                  const text = tweetText ? tweetText.innerText : '';
                  if (!text) continue;

                  // 作者
                  const userLink = art.querySelector('a[role="link"][href^="/"]:not([href*="status"])');
                  const authorMatch = userLink ? userLink.getAttribute('href') : '';
                  const handle = authorMatch.replace(/^\\//, '').split('/')[0];

                  // 发布时间
                  const timeEl = art.querySelector('time');
                  const datetime = timeEl ? timeEl.getAttribute('datetime') : null;

                  // 互动数：按 aria-label 抽
                  const groupTexts = [];
                  art.querySelectorAll('[role="group"] [aria-label]').forEach(el => {
                    groupTexts.push(el.getAttribute('aria-label'));
                  });
                  const allLabels = groupTexts.join(' ');

                  out.push({
                    url: tweetUrl,
                    text: text,
                    handle: handle,
                    datetime: datetime,
                    metrics_raw: allLabels,
                  });
                } catch (e) { /* skip */ }
              }
              return out;
            }"""
        )

        items: List[FetchedItem] = []
        seen_urls: set[str] = set()
        for r in raw_list:
            url = r.get("url")
            text = (r.get("text") or "").strip()
            if not url or not text or url in seen_urls:
                continue
            seen_urls.add(url)

            handle = r.get("handle") or ""
            datetime_str = r.get("datetime")
            published_at = None
            if datetime_str:
                try:
                    # ISO 8601 with Z
                    published_at = datetime.fromisoformat(datetime_str.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    pass

            # 解析互动数据（aria-label 包含 "1.2K replies, 3.4K likes, 5.6M views"）
            metrics_raw = r.get("metrics_raw") or ""
            replies = self._extract_count(metrics_raw, ["replies", "回复"])
            likes = self._extract_count(metrics_raw, ["likes", "Likes", "喜欢"])
            views = self._extract_count(metrics_raw, ["views", "Views", "次观看"])
            retweets = self._extract_count(metrics_raw, ["reposts", "Reposts", "转推"])

            # 推文标题用前 80 字
            title = text.split("\n")[0][:120]
            if len(text) > len(title):
                title = title + ("..." if not title.endswith("...") else "")

            items.append(FetchedItem(
                title=title,
                url=url,
                summary=text[:500] if text else None,
                author=f"@{handle}" if handle else None,
                published_at=published_at,
                engagement={
                    "like": likes,
                    "comments": replies,
                    "retweet": retweets,
                    "views": views,
                    "interactive": likes + replies + retweets,
                },
                extras={
                    "tweet_url": url,
                    "x_handle": handle,
                    "discovered_from": source_url,
                },
            ))
            if len(items) >= limit:
                break

        return items

    @staticmethod
    def _extract_count(text: str, keywords: List[str]) -> int:
        """从 'X likes' / 'X 喜欢' 类标签里抠数字。"""
        for kw in keywords:
            m = re.search(rf"([\d.,]+\s*[KMB万千]?)\s*{kw}", text, re.IGNORECASE)
            if m:
                return _parse_metric(m.group(1))
        return 0

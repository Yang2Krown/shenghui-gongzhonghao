"""爆文套路研究（v2）。

两轴，都走搜狗公众号搜索（Exa 已弃用）：
  - 公众号爆文（本品）：搜产品名，学开头钩子 / 结构 / 卖点呈现
  - 竞品商稿爆文：搜竞品名 + 测评/推荐，学软植入手法 / 差异点 / 避雷

每轴 top3 截断后一次性总结（量小，没必要逐篇 map-reduce），多轴并行。
产出 HotResearch，挂到 ProductResearch.hot，最终进正文的 topic_routine。
"""

import asyncio
import logging
from typing import Callable, List, Optional, Tuple

from app.core.config import settings
from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage
from app.services.practical_creation.schemas import HotResearch

logger = logging.getLogger(__name__)

_BODY_CHARS = 2000          # 每篇正文截断长度
_TOP_N = 3                  # 每轴取前几篇

_SUMMARY_SYS = """你在拆解爆款公众号文章的"套路"，不是复述它讲了什么。
针对给定的几篇文章，提炼共性套路，输出 3-5 条，每条一句话，聚焦：
- 开头怎么钩住读者（痛点/悬念/反差/数据）
- 整体结构怎么排
- 产品/卖点怎么呈现（硬广还是软植入、怎么不招人烦）
只输出要点，不要客套。"""

_COMPETITOR_EXTRA = "这是竞品的软文，额外提炼：它怎么软植入、强调哪些差异点、有什么可借鉴或要避开的。"


async def _summarize_axis(kind: str, articles: List[dict], competitor: bool) -> str:
    """把一轴的若干篇文章总结成套路要点。"""
    if not articles:
        return ""
    blocks = []
    for i, a in enumerate(articles, 1):
        body = (a.get("content") or "")[:_BODY_CHARS]
        blocks.append(f"【文章{i}】{a.get('title', '')}\n{body}")
    sys = _SUMMARY_SYS + ("\n" + _COMPETITOR_EXTRA if competitor else "")
    client = get_llm_client("deepseek")  # 压缩用便宜档
    res = await client.chat(
        [ChatMessage(role="system", content=sys),
         ChatMessage(role="user", content="\n\n".join(blocks))],
        max_tokens=600,
    )
    return (res.text or "").strip()


async def _fetch_wechat_articles(keyword: str, limit: int) -> List[dict]:
    """公众号文章搜索。优先级：博查（国内可充值、扛量）→ Exa → 搜狗兜底。返回 [{title,url,content}]。"""
    # 博查：限定 mp.weixin.qq.com 域名，summary/snippet 当正文初稿（够分析套路）
    if settings.BOCHA_API_KEY:
        try:
            from app.services.practical_creation.bocha import bocha_search
            hits = await bocha_search(keyword, count=limit, wechat_only=True)
            arts = [
                {"title": h["title"], "url": h["url"], "content": h["summary"] or h["snippet"]}
                for h in hits if (h.get("summary") or h.get("snippet"))
            ]
            if arts:
                return arts[:limit]
            logger.info(f"[爆文研究] 博查无结果，回落 Exa/搜狗: {keyword}")
        except Exception as e:
            logger.warning(f"[爆文研究] 博查调用失败，回落: {e}")
    if settings.EXA_API_KEY:
        from app.services.agent_reach_client import agent_reach_client
        hits = await agent_reach_client.search_wechat(keyword, num_results=limit)
        out = []
        for h in hits[:limit]:
            url = h.get("url")
            if not url:
                continue
            try:
                content = await agent_reach_client.crawl_wechat([url], max_characters=_BODY_CHARS)
            except Exception:
                content = h.get("snippet", "")
            if content:
                out.append({"title": h.get("title", ""), "url": url, "content": content})
        return out
    # 搜狗兜底
    from app.services.scraping.adapters.sogou_wechat_adapter import SogouWechatAdapter
    return await SogouWechatAdapter().search_articles(keyword, limit)


async def _run_axis(kind: str, keyword: str, competitor: bool) -> Tuple[str, str, List[str]]:
    """搜一轴 → 取 top N → 总结。返回 (kind, 套路文本, 来源链接)。"""
    try:
        articles = await _fetch_wechat_articles(keyword, limit=_TOP_N + 2)
    except Exception as e:
        logger.warning(f"[爆文研究] {kind} 搜索失败: {e}")
        return kind, "", []
    articles = articles[:_TOP_N]
    summary = await _summarize_axis(kind, articles, competitor)
    sources = [a["url"] for a in articles if a.get("url")]
    return kind, summary, sources


async def research_hot(
    product: str,
    axes: Optional[List[str]] = None,
    competitor: str = "",
    progress_callback: Optional[Callable] = None,
) -> HotResearch:
    """爆文套路研究。axes 取值：'gzh'（公众号本品）、'competitor'（竞品）。"""
    axes = axes or ["gzh"]

    jobs = []
    if "gzh" in axes:
        jobs.append(_run_axis("公众号爆文", product, competitor=False))
    if "competitor" in axes and competitor.strip():
        jobs.append(_run_axis("竞品商稿", f"{competitor.strip()} 测评 推荐", competitor=True))

    if not jobs:
        return HotResearch()

    if progress_callback:
        await progress_callback({"event": "step_start", "data": {
            "step": 1, "agent": "爆文研究员",
            "action": f"正在搜公众号 / 竞品爆文，学开头钩子与结构…（{len(jobs)} 轴）",
            "avatar": "/agents/source.png"}})

    results = await asyncio.gather(*jobs, return_exceptions=True)

    parts, sources = [], []
    for r in results:
        if isinstance(r, Exception) or not r:
            continue
        kind, summary, srcs = r
        if summary:
            parts.append(f"【{kind}套路】\n{summary}")
            sources.extend(srcs)

    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": 1, "agent": "爆文研究员"}})

    return HotResearch(patterns="\n\n".join(parts), sources=sources)


# ── ponytail 自检：纯合并逻辑，不联网不调模型 ──
def _demo():
    g = globals()  # 避免 -m 双模块：patch 当前正在执行的模块

    async def fake_axis(kind, keyword, competitor):
        return kind, f"{kind} 的套路要点", [f"http://x/{kind}"]
    orig = g["_run_axis"]
    g["_run_axis"] = fake_axis
    try:
        hot = asyncio.get_event_loop().run_until_complete(
            research_hot("某产品", axes=["gzh", "competitor"], competitor="对手"))
        assert "公众号爆文套路" in hot.patterns, hot.patterns
        assert "竞品商稿套路" in hot.patterns, hot.patterns
        assert len(hot.sources) == 2, hot.sources
        # competitor 轴缺竞品名时应被跳过
        hot2 = asyncio.get_event_loop().run_until_complete(
            research_hot("某产品", axes=["gzh", "competitor"], competitor=""))
        assert "竞品" not in hot2.patterns, hot2.patterns
        print("hot_research merge self-check OK")
    finally:
        g["_run_axis"] = orig


if __name__ == "__main__":
    _demo()

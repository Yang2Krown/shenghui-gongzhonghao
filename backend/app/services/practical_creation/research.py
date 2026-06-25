"""产品研究：迭代搜索（最多 3 轮，AI 判断够不够、不够就换词）+ 抓教程全文 → 提炼结构化研究。

- 迭代搜索：搜 10 条 → deepseek 看够不够、有没有噪音 → 不够就换关键词再搜，最多 3 轮。
  DeepSeek 无状态，所以把每轮的 query + 结果标题累积进 messages 一起传，裁判才有"记忆"。
- 抓全文：对教程类页面抓正文，供提炼真实操作步骤（国内服务器走 webfetch 直连）。
"""

import asyncio
import logging
from typing import Callable, List, Optional

from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose
from app.services.practical_creation.bocha import bocha_search
from app.services.practical_creation.webfetch import fetch_many
from app.services.practical_creation.schemas import ProductResearch

logger = logging.getLogger(__name__)

_HOWTO_HINTS = ("教程", "怎么", "使用", "入门", "上手", "指南", "教学", "操作", "step", "如何")
_MAX_ROUNDS = 3

# 只在这些优质平台里搜（白名单）：解决"结果太散、混进文档站/软件下载站/公益站"的问题。
# 注：博查的公众号(mp.weixin)索引又少又旧（新品基本搜到 0），加了也没用，故不放进来；
# 真要公众号最新教程得走搜狗或新榜，博查做不了。
_GOOD_DOMAINS = "|".join([
    "zhihu.com", "csdn.net", "juejin.cn", "jianshu.com", "sspai.com",
    "woshipm.com", "cnblogs.com", "segmentfault.com", "36kr.com",
    "ifanr.com", "infoq.cn",
])

JUDGE_SYS = """你是产品调研员，边搜边判断。目标：攒够资料写一篇实操指南，覆盖三要素——产品定位、主要功能、典型使用步骤。

关键：资料是「所有结果合起来」评估，**不要求单篇文章覆盖全部**；只要累计结果里这三方面都能找到出处，就算够了。
别追求完美的综合性文章（那几乎不存在），基本覆盖到就给 enough=true，避免无谓多搜。

每轮我给你本轮搜索词和结果标题。请：
1. 判断三要素里目前还缺哪些（missing，没缺就空数组）
2. enough：三要素基本都有来源、或资料量已够写，就 true
3. 若不够，针对【缺的方面】给一个更聚焦的中文搜索词（换角度/加限定/用产品全称），别和已试过的重复

只输出 JSON：{"enough": true/false, "missing": ["缺的方面"], "next_query": "若不够才给", "reason": "一句话说明"}"""

RESEARCH_SYSTEM = """你是产品调研员。下面给你一个产品名、可选的商单 brief，以及一批联网搜索/教程全文。
基于这些信息把产品调研清楚，输出严格的 JSON（不要任何额外文字）。
注意：advantages 放在 features 前面，必须先写完整，别因为后面 features 太长而漏掉。
{
  "positioning": "产品定位，一两句话说清它是什么、给谁用",
  "advantages": ["产品优势1", "产品优势2", "产品优势3"],
  "features": [
    {"name": "功能点名称", "desc": "一句话说明",
     "steps": ["操作步骤1", "操作步骤2"],
     "recommend": true, "reason": "为何建议/不建议做成实操段"}
  ],
  "insufficient": false
}

要求：
- features 给 4-6 个，按是否适合写成「实操演示段」给 recommend（核心高频功能 true，边缘/无截图价值 false）。
- steps：从教程全文里提炼该功能的真实操作步骤（如"进入X→点击Y→设置Z"），3-5 步；
  资料里没讲到操作的功能，steps 给空数组 []，不要编造不存在的按钮/路径。
- 只用所给材料里的信息，别编造具体数字；信息明显不足时把 insufficient 设为 true。"""


async def _iterative_search(product: str, brief: str, push: Callable) -> List[dict]:
    """迭代搜索：最多 3 轮，AI 判断够不够、不够换词。返回去重后的累计结果。"""
    client = get_llm_client("deepseek")
    messages = [ChatMessage(role="system", content=JUDGE_SYS)]
    query = f"{product} 是什么 功能 使用教程 怎么用"
    seen: dict = {}
    tried: List[str] = []

    for rnd in range(1, _MAX_ROUNDS + 1):
        await push(f"第 {rnd}/{_MAX_ROUNDS} 轮搜索：{query}")
        try:
            # 白名单优质平台(含公众号) + 近一个月：只要新产品的最新教程
            hits = await bocha_search(query, count=10, include=_GOOD_DOMAINS, freshness="oneMonth")
        except Exception as e:
            logger.warning(f"[产品研究] 第{rnd}轮博查失败: {e}")
            hits = []
        for h in hits:
            u = h.get("url")
            if u and u not in seen:
                seen[u] = h
        tried.append(query)

        if rnd == _MAX_ROUNDS:
            break

        # 带上摘要，裁判才能真判断覆盖了啥（只给标题会一直保守地说"都缺"）
        listing = "\n".join(
            f"- {h.get('title', '')}：{(h.get('summary') or h.get('snippet') or '')[:90]}"
            for h in hits) or "(本轮无结果)"
        messages.append(ChatMessage(role="user", content=(
            f"产品：{product}\nbrief：{brief or '无'}\n"
            f"第{rnd}轮搜索词「{query}」，结果（标题：摘要）：\n{listing}\n\n"
            f"已累计 {len(seen)} 条。够写实操指南了吗？已试过的搜索词：{tried}")))
        try:
            # 调大：deepseek 推理模型会先吃掉一段 reasoning，给足空间避免 JSON 被截
            res = await client.chat(messages, max_tokens=2000)
        except Exception as e:
            logger.warning(f"[产品研究] 裁判调用失败，停止迭代: {e}")
            break
        messages.append(ChatMessage(role="assistant", content=res.text))  # 累积记忆

        data = parse_json_loose(res.text) or {}
        missing = data.get("missing") or []
        reason = data.get("reason", "")
        if data.get("enough"):
            await push(f"资料已够（{len(seen)} 条）：{reason}")
            break
        # 把缺口分析显示出来，让你看到 AI 是针对缺啥在补搜
        gap = "、".join(missing) if missing else reason
        await push(f"第{rnd}轮发现还缺：{gap}，针对性补搜…")
        nq = (data.get("next_query") or "").strip()
        if not nq or nq in tried:
            break
        query = nq

    return list(seen.values())


async def research_product(
    product: str,
    brief: str = "",
    progress_callback: Optional[Callable] = None,
) -> ProductResearch:
    """调研产品，返回 ProductResearch（含每个功能的操作步骤）。"""
    async def _push(action: str):
        if progress_callback:
            await progress_callback({"event": "step_start", "data": {
                "step": 0, "agent": "产品调研员", "action": action,
                "avatar": "/agents/source.png"}})

    hits = await _iterative_search(product, brief, _push)

    # 优先抓"教程/怎么用"类页面的全文（实操步骤的真正来源）；多抓几篇 = 更多功能能提炼出步骤
    ranked = sorted(hits, key=lambda h: any(k in (h.get("title", "")) for k in _HOWTO_HINTS), reverse=True)
    deep_urls = [h["url"] for h in ranked[:6] if h.get("url")]
    fulltext = {}
    if deep_urls:
        await _push("正在抓取教程全文…")
        try:  # 整体兜底：抓取再慢也不拖死整个研究
            fulltext = await asyncio.wait_for(fetch_many(deep_urls, max_chars=6000), timeout=45)
        except asyncio.TimeoutError:
            logger.warning("[产品研究] 教程抓取整体超时，跳过全文用摘要")

    await _push("正在提炼定位、功能点与操作步骤…")
    parts = []
    for h in hits[:15]:
        body = fulltext.get(h.get("url", "")) or h.get("summary") or h.get("snippet") or ""
        if body:
            parts.append(f"标题：{h.get('title', '')}\n内容：{body}\n来源：{h.get('url', '')}")
    corpus = "\n\n".join(parts)
    user = (
        f"产品名：{product}\n"
        f"商单 brief：{brief or '无'}\n\n"
        f"联网搜索/教程内容：\n{corpus or '（没搜到，凭产品名与 brief 推断，并把 insufficient 设为 true）'}"
    )

    client = get_llm_client("deepseek")
    res = await client.chat(
        [ChatMessage(role="system", content=RESEARCH_SYSTEM),
         ChatMessage(role="user", content=user)],
        max_tokens=8000,  # 质量优先，给足空间写全功能点+步骤+优势
    )

    data = parse_json_loose(res.text) or {}
    data.setdefault("product", product)
    research = ProductResearch.from_dict(data)
    research.product = product
    research.sources = [h["url"] for h in hits[:15] if h.get("url")]
    research.references = [  # 前端只展示标题 + 链接
        {"title": h.get("title", ""), "url": h.get("url", "")}
        for h in hits[:15] if h.get("url")
    ]

    if not research.features:
        logger.warning(f"[产品研究] 解析不到功能点，标记信息不足。原始：{res.text[:300]}")
        research.insufficient = True

    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": 0, "agent": "产品调研员"}})
    return research


# ── ponytail 自检：纯解析逻辑，不联网 ──
def _demo():
    raw = {
        "positioning": "AI 排版工具",
        "features": [
            {"name": "一键排版", "desc": "MD 转公众号",
             "steps": ["粘贴正文", "选主题", "点导出"], "recommend": True, "reason": "核心"},
            {"name": "团队协作", "steps": [], "recommend": False, "reason": "边缘"},
            {"name": "", "desc": "应被丢弃"},
        ],
        "advantages": ["快", "  "],
        "insufficient": False,
    }
    r = ProductResearch.from_dict(raw)
    assert len(r.features) == 2, r.features
    assert r.features[0].steps == ["粘贴正文", "选主题", "点导出"], r.features[0].steps
    assert "步骤1：粘贴正文" in r.to_material_text()
    print("research parser self-check OK")


if __name__ == "__main__":
    _demo()

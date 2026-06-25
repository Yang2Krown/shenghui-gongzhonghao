"""产品研究：博查搜教程站 + Exa 搜公众号 → 合并候选 → 筛选 → 抓全文 → 提炼结构化研究。

- 教程站迭代搜索：博查搜 10 条 → deepseek 看够不够 → 不够就换关键词再搜，最多 3 轮。
  DeepSeek 无状态，所以把每轮的 query + 结果标题累积进 messages 一起传，裁判才有"记忆"。
- 公众号搜索：Exa 限定 mp.weixin 域名搜爆文（博查公众号索引太旧用不了），并入候选池。
- 筛选（启发式预筛 + AI 选）：去重 / 同域名限量 / 公众号·教程优先，再让 deepseek 挑最相关 N 篇，
  避免一股脑全塞稀释 prompt、拉低生成质量。筛后的 references 既前端展示、也喂正文生成。
- 抓全文：教程站走 webfetch 直连；公众号直连会被"请在客户端打开"挡，必须走 Exa crawl。
"""

import asyncio
import logging
from typing import Callable, List, Optional
from urllib.parse import urlparse

from app.core.config import settings
from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose
from app.services.practical_creation.bocha import bocha_search
from app.services.practical_creation.webfetch import fetch_many
from app.services.practical_creation.schemas import ProductResearch

logger = logging.getLogger(__name__)

_HOWTO_HINTS = ("教程", "怎么", "使用", "入门", "上手", "指南", "教学", "操作", "step", "如何")
_MAX_ROUNDS = 3

# 筛选参数
_WECHAT_NUM = 8          # Exa 公众号搜回多少条候选（公众号是首选源，够了就不搜博查，故给足）
_WECHAT_BODY = 3000      # 公众号搜回时一并取的正文长度（复用作筛选摘要 + 正文，省掉额外 crawl 调用）
_WECHAT_ENOUGH = 99      # 公众号独占模式几乎不触发——公众号缺操作步骤，始终补搜博查教程站
_PER_DOMAIN_CAP = 2      # 预筛时同一教程站最多保留几篇（避免 8 篇全是 CSDN）
_WECHAT_CAP = 4          # 混搭模式下公众号占比上限；公众号独占模式不受此限
_FINAL_K = 8             # AI 最终选出、喂生成 / 显示的参考资料条数

# 只在这些优质平台里搜（白名单）：解决"结果太散、混进文档站/软件下载站/公益站"的问题。
# 注：博查的公众号(mp.weixin)索引又少又旧（新品基本搜到 0），公众号那路改走 Exa，见 _search_wechat。
_GOOD_DOMAINS = "|".join([
    "zhihu.com", "csdn.net", "juejin.cn", "jianshu.com", "sspai.com",
    "woshipm.com", "cnblogs.com", "segmentfault.com", "36kr.com",
    "ifanr.com", "infoq.cn",
])

# 域名 → 中文站点名（前端 source 标签 + 预筛分组用）
_DOMAIN_NAMES = {
    "zhihu.com": "知乎", "csdn.net": "CSDN", "juejin.cn": "掘金", "jianshu.com": "简书",
    "sspai.com": "少数派", "woshipm.com": "人人都是产品经理", "cnblogs.com": "博客园",
    "segmentfault.com": "思否", "36kr.com": "36氪", "ifanr.com": "爱范儿", "infoq.cn": "InfoQ",
}


def _host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def _domain_label(url: str) -> str:
    host = _host(url)
    for d, name in _DOMAIN_NAMES.items():
        if d in host:
            return name
    return host or "网页"


def _is_howto(title: str) -> bool:
    return any(k in (title or "") for k in _HOWTO_HINTS)


def _norm_platform(h: dict) -> dict:
    """博查教程站结果归一化为 {title,url,summary,source}。"""
    return {
        "title": h.get("title", ""),
        "url": h.get("url", ""),
        "summary": h.get("summary") or h.get("snippet") or "",
        "source": _domain_label(h.get("url", "")),
    }


def _is_junk_wechat(h: dict) -> bool:
    """Exa 抓近期公众号常被微信"请在客户端打开"拦截，缓存的是拦截页样板（标题恒为
    'Weixin Official Accounts Platform'、正文是 meta 样板）。这类无正文价值，直接丢。"""
    title = h.get("title", "") or ""
    return (not title.strip()) or ("Weixin Official Accounts Platform" in title)


def _mentions(h: dict, product: str) -> bool:
    """文章标题或正文里真提到产品名才算相关。

    Exa 神经搜索对任何词都会返回一批"语义最近"的公众号（冷门/乱码产品也能返回 7-8 篇擦边文），
    所以判断公众号"够不够"不能只看数量，要看真提到产品的有几篇。"""
    p = (product or "").strip().lower()
    if not p:
        return False
    blob = (h.get("title", "") + " " + h.get("summary", "")).lower()
    return p in blob


def _norm_wechat(h: dict) -> dict:
    """Exa 公众号结果归一化。"""
    return {
        "title": h.get("title", ""),
        "url": h.get("url", ""),
        "summary": h.get("snippet") or "",
        "source": "公众号",
    }


async def _search_wechat(product: str, num: int = _WECHAT_NUM) -> List[dict]:
    """Exa 搜公众号爆文（连正文一并搜回，省掉额外 crawl）。无 key / 失败都返回空，绝不打断主流程。

    不加发布日期过滤：实测一加 startPublishedDate，Exa 就只返回"最近抓但被微信拦"的
    junk 拦截页（0 篇真正文）；不加才按相关度返回它早抓好、正文完整的热门文。
    """
    if not settings.EXA_API_KEY:
        logger.warning("[产品研究] EXA_API_KEY 未配置，跳过公众号搜索")
        return []
    try:
        from app.services.agent_reach_client import agent_reach_client
        raw = await agent_reach_client.search_wechat(product, num_results=num, text_chars=_WECHAT_BODY)
        logger.info(f"[产品研究] Exa 公众号原始结果: {len(raw)} 条")
        filtered = [_norm_wechat(h) for h in raw if h.get("url") and not _is_junk_wechat(h)]
        logger.info(f"[产品研究] 过滤后公众号: {len(filtered)} 条")
        for i, h in enumerate(filtered[:3]):
            logger.info(f"  [{i}] {h['title'][:40]}  summary_len={len(h.get('summary',''))}")
        return filtered
    except Exception as e:
        logger.warning(f"[产品研究] 公众号(Exa)搜索失败，跳过: {type(e).__name__}: {e}")
        return []


def _prefilter(cands: List[dict], wechat_cap: int = _WECHAT_CAP) -> List[dict]:
    """启发式预筛：公众号 / 教程标题优先排序 → 去重 + 同域名限量 + 丢空摘要。

    wechat_cap：公众号占比上限；公众号独占模式传 _FINAL_K 即不限量。
    """
    ranked = sorted(
        cands,
        key=lambda h: (h.get("source") != "公众号", not _is_howto(h.get("title", ""))),
    )
    seen: set = set()
    per: dict = {}
    out: List[dict] = []
    for h in ranked:
        u = h.get("url")
        if not u or u in seen or not h.get("summary"):
            continue
        group = h.get("source") or _host(u)
        cap = wechat_cap if group == "公众号" else _PER_DOMAIN_CAP
        if per.get(group, 0) >= cap:
            continue
        seen.add(u)
        per[group] = per.get(group, 0) + 1
        out.append(h)
    return out


_SELECT_SYS = """你在为一篇产品实操指南筛选参考资料。给你产品名、可选 brief，和一批候选（编号 + 来源 + 标题 + 摘要）。
挑出最该保留的不超过 {k} 篇：优先与产品强相关、含真实操作 / 功能讲解、信息密度高的；
剔除蹭词、宽泛、与产品无关、纯营销无干货的。公众号爆文若与产品相关要保留（学开头钩子与表达）。
只输出 JSON：{{"keep": [编号...]}}，按相关度从高到低。"""


async def _ai_select(product: str, brief: str, cands: List[dict], k: int = _FINAL_K) -> List[dict]:
    """从预筛候选里让 deepseek 选最相关的 k 篇。失败 / 不够则退回前 k 篇。"""
    if len(cands) <= k:
        return cands
    listing = "\n".join(
        f"[{i}] ({h.get('source', '')}) {h.get('title', '')}：{(h.get('summary') or '')[:120]}"
        for i, h in enumerate(cands)
    )
    client = get_llm_client("deepseek")
    try:
        res = await client.chat(
            [ChatMessage(role="system", content=_SELECT_SYS.format(k=k)),
             ChatMessage(role="user", content=f"产品：{product}\nbrief：{brief or '无'}\n候选：\n{listing}")],
            max_tokens=1500,  # deepseek 推理模型先吃一段 reasoning，给足空间避免 JSON 被截
        )
        data = parse_json_loose(res.text) or {}
        keep = [i for i in (data.get("keep") or []) if isinstance(i, int) and 0 <= i < len(cands)]
        if keep:
            return [cands[i] for i in keep[:k]]
    except Exception as e:
        logger.warning(f"[参考资料筛选] AI 选择失败，退回启发式前 {k}: {e}")
    return cands[:k]


async def _fetch_fulltext(curated: List[dict]) -> dict:
    """深抓筛后教程站正文（webfetch 直连，免费）。返回 {url: 正文}。

    公众号正文在 _search_wechat 时已随搜索一并取回（在 summary 里），不再单独 crawl——
    省掉那几次 Exa /contents 调用（每条按内容费收钱）。
    """
    web_urls = [c["url"] for c in curated if c.get("source") != "公众号" and c.get("url")]
    if not web_urls:
        return {}
    try:  # 整体兜底：抓取再慢也不拖死整个研究
        return await asyncio.wait_for(fetch_many(web_urls, max_chars=6000), timeout=45)
    except asyncio.TimeoutError:
        logger.warning("[产品研究] 教程全文抓取整体超时，跳过用摘要")
        return {}

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

    # 公众号优先：先搜公众号（近一个月，含正文）。够了就只用公众号、不再搜博查；
    # 不够才补搜博查教程站（知乎/CSDN）凑足资料。
    await _push("正在搜公众号爆文…")
    wechat_hits = [
        h for h in await _search_wechat(product)
        if h.get("summary") and _mentions(h, product)  # 精确匹配产品名，避免语义搜索的擦边文
    ]

    if len(wechat_hits) >= _WECHAT_ENOUGH:
        await _push(f"公众号已搜到 {len(wechat_hits)} 篇相关爆文，资料充足，只用公众号")
        cands = wechat_hits
        wechat_cap = _FINAL_K  # 独占模式：公众号不限量
    else:
        await _push(f"相关公众号仅 {len(wechat_hits)} 篇，补搜知乎/CSDN 等平台凑足资料…")
        platform_hits = await _iterative_search(product, brief, _push)
        cands = [_norm_platform(h) for h in platform_hits if h.get("url")] + wechat_hits
        wechat_cap = _WECHAT_CAP

    # 启发式预筛 → AI 选最相关 N 篇（避免太多稀释 prompt）
    await _push("正在筛选最相关的参考资料…")
    curated = await _ai_select(product, brief, _prefilter(cands, wechat_cap=wechat_cap), k=_FINAL_K)
    wx_n = sum(1 for c in curated if c.get("source") == "公众号")
    await _push(f"筛选出 {len(curated)} 篇参考资料（含公众号 {wx_n} 篇），正在抓全文…")

    # 深抓筛后参考资料正文（教程站直连 / 公众号走 Exa），抓到的回填进 summary 一并喂生成
    fulltext = await _fetch_fulltext(curated)
    for c in curated:
        body = fulltext.get(c["url"])
        if body:
            c["summary"] = body

    await _push("正在提炼定位、功能点与操作步骤…")
    parts = [
        f"标题：{c['title']}\n内容：{c['summary']}\n来源：{c['url']}"
        for c in curated if c.get("summary")
    ]
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
    research.sources = [c["url"] for c in curated]
    research.references = [  # 前端展示 + 喂生成；带 source 标签区分公众号 / 教程站
        {"title": c["title"], "url": c["url"],
         "summary": (c.get("summary") or "")[:300], "source": c.get("source", "")}
        for c in curated
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

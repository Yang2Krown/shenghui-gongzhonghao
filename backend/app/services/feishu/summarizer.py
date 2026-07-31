"""把商单 brief 原文 → 结构化 StructuredBrief（LLM）。

与来源无关：飞书文档 / 粘贴文本 / 上传文件提取出的原文都走这里。
输出对齐 practical 流程所需字段（product / brief / banned / tone），
并额外抽取检查环节要用的 must_cover 等。
"""

import logging
import re
from typing import Optional

from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose

logger = logging.getLogger(__name__)

# 喂给 LLM 的原文上限。DeepSeek-V3 上下文 64K，30K 字符（约 2 万 token）很安全。
# 商单 brief 常把「禁忌/红线」「审核要求」「发布时间」放在文档末尾，
# 简单从头砍会整段丢失，导致 banned/must_cover/publish 字段为空（看似“解析被截断”）。
_MAX_INPUT_CHARS = 30000

# 命中这些词的段落，在超长截断时优先保留（多为 brief 尾部的高价值约束）。
_KEY_FIELD_RE = re.compile(
    r"禁忌|红线|不得|禁止|必须|务必|勿|审核|审稿|确认|档期|发布时间|发布|排期|"
    r"违禁|敏感|合规|注意事项|附加|备注|邀约|福利|优惠|链接|邀请码",
    re.IGNORECASE,
)


def _smart_truncate(text: str, limit: int = _MAX_INPUT_CHARS) -> str:
    """超长时智能截断：保开头 + 优先保留含关键约束词的段落，避免尾部红线/审核丢失。"""
    if len(text) <= limit:
        return text

    paragraphs = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    head_budget = int(limit * 0.6)   # 开头背景/产品介绍占 60%
    tail_budget = limit - head_budget  # 关键段落占 40%

    head_parts, used = [], 0
    for p in paragraphs:
        if used + len(p) > head_budget:
            # 该段放不下：若开头还没收到任何内容，按字符切下开头的剩余额度，
            # 避免“第一段就是巨段”导致开头全丢。
            if not head_parts:
                head_parts.append(text[:head_budget])
                used = head_budget
            break
        head_parts.append(p)
        used += len(p)
    head_text = "\n".join(head_parts)

    # 从全文收集命中关键词的段落（保持原顺序、去掉已进开头的），塞进剩余预算
    key_parts, used_tail = [], 0
    for p in paragraphs:
        if p in head_parts or p in head_text:
            continue
        if _KEY_FIELD_RE.search(p) and used_tail + len(p) <= tail_budget:
            key_parts.append(p)
            used_tail += len(p)

    kept = head_parts + key_parts
    logger.info(
        f"[brief 总结] 原文 {len(text)} 字超上限，智能截断为 {sum(len(p) for p in kept)} 字"
        f"（开头 {len(head_parts)} 段 + 关键段落 {len(key_parts)} 段）"
    )
    return "\n".join(kept)

_SYS = """你是商单 brief 分析助手。下面是品牌方给博主的「商单写作要求」原文（可能含排版噪音、表格、图片占位）。
请把它归纳成结构化 JSON，**只输出 JSON**，字段如下（缺失填 null 或空数组，不要编造）：

{
  "product": "被推广的产品/工具名（最核心的那个）",
  "brief": "提炼后的写作要求正文，3-8 句话讲清楚要写什么、怎么写、核心信息",
  "core_message": "品牌方最想传达的一句话主张（slogan/核心卖点），没有则 null",
  "must_cover": ["必须覆盖/展示的要点，逐条", "如：具体案例、某功能、活动信息"],
  "tone": "调性与表达要求（如：通俗易懂、避免术语），没有则 null",
  "banned": ["红线/禁忌，逐条", "如：不得提及竞品、不得拼广、不得删改品牌信息"],
  "cta": "引导动作（如：评论区领福利、放专属链接/邀请码），没有则 null",
  "audience": "目标读者，没有则 null",
  "publish": "发布档期/时间要求，没有则 null",
  "review_notes": "审核/交付要求（如需品牌方确认、提供生成链接等），没有则 null",
  "notes": "其他约束（字数、平台、字段补充），没有则 null"
}"""


async def summarize_brief(raw_text: str, title: str = "") -> dict:
    """原文 → StructuredBrief dict。失败时退回仅含 brief 原文的最小结构。"""
    text = raw_text.strip()
    if not text:
        return _fallback("", title)

    user = (f"文档标题：{title}\n\n" if title else "") + f"原文：\n{_smart_truncate(text)}"
    client = get_llm_client()
    try:
        res = await client.chat(
            [ChatMessage(role="system", content=_SYS),
             ChatMessage(role="user", content=user)],
            max_tokens=4000,  # deepseek 推理模型先吃 reasoning，给足空间避免 JSON 被截
            json_mode=True,
        )
        data = res.parsed or parse_json_loose(res.text)
        if not data:
            logger.warning("[brief 总结] LLM 输出无法解析 JSON，退回原文")
            return _fallback(text, title)
        return _normalize(data, title)
    except Exception as e:
        logger.error(f"[brief 总结] 失败: {e}", exc_info=True)
        return _fallback(text, title)


def _normalize(data: dict, title: str) -> dict:
    """补齐字段、统一类型。"""
    def _list(v):
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        return []

    def _str(v) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    return {
        "product": _str(data.get("product")) or (title or ""),
        "brief": _str(data.get("brief")) or "",
        "core_message": _str(data.get("core_message")),
        "must_cover": _list(data.get("must_cover")),
        "tone": _str(data.get("tone")),
        "banned": _list(data.get("banned")),
        "cta": _str(data.get("cta")),
        "audience": _str(data.get("audience")),
        "publish": _str(data.get("publish")),
        "review_notes": _str(data.get("review_notes")),
        "notes": _str(data.get("notes")),
    }


def _fallback(text: str, title: str) -> dict:
    return {
        "product": title or "",
        "brief": text,
        "core_message": None,
        "must_cover": [],
        "tone": None,
        "banned": [],
        "cta": None,
        "audience": None,
        "publish": None,
        "review_notes": None,
        "notes": None,
    }

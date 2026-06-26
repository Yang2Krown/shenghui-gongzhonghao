"""把商单 brief 原文 → 结构化 StructuredBrief（LLM）。

与来源无关：飞书文档 / 粘贴文本 / 上传文件提取出的原文都走这里。
输出对齐 practical 流程所需字段（product / brief / banned / tone），
并额外抽取检查环节要用的 must_cover 等。
"""

import logging
from typing import Optional

from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose

logger = logging.getLogger(__name__)

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

    user = (f"文档标题：{title}\n\n" if title else "") + f"原文：\n{text[:12000]}"
    client = get_llm_client()
    try:
        res = await client.chat(
            [ChatMessage(role="system", content=_SYS),
             ChatMessage(role="user", content=user)],
            max_tokens=3000,  # deepseek 推理模型先吃 reasoning，给足空间避免 JSON 被截
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

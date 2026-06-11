"""用户文本事实提取器。

从用户上传的内容（文件/链接/文本）中提取关键事实，
生成「事实素材包」供续写/润色工具使用，降低幻觉。

与 source_collector.py 的区别：
- source_collector: 从数据库 RawInfo 提取，面向正文生成管线
- user_source_extractor: 从用户直接提供的文本提取，面向创作工具
"""

import logging
from typing import Optional

from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose

logger = logging.getLogger(__name__)


EXTRACTION_SYSTEM_PROMPT = """你是事实提取专家。从用户提供的文本中提取所有具体事实。

具体事实包括：数字、日期、时间、人名、产品名、版本号、价格、机构名、公司名、
技术参数、URL、引用、事件、案例、数据统计。

不要提取：观点、评论、分析、比喻、修辞手法、通用常识。

只输出 JSON，不要解释。"""


def _build_extraction_prompt(text: str, task_type: str = "general") -> str:
    """构建事实提取提示词。

    Args:
        text: 用户原文
        task_type: 任务类型 - "continuation"（续写）/ "polish"（润色）/ "general"
    """
    lines = []
    lines.append("请从以下文本中提取所有具体事实。")
    lines.append("")

    if task_type == "continuation":
        lines.append("【场景】用户要续写这篇文章。续写时必须保持与原文事实一致，不能编造新的具体信息。")
        lines.append("请特别关注：文中提到的数字、时间线、人物、产品、事件——这些是续写时必须延续的事实线索。")
    elif task_type == "polish":
        lines.append("【场景】用户要润色/改写这篇文章。改写时必须保留所有具体事实，不能篡改数据或编造新信息。")
    else:
        lines.append("【场景】提取文本中的关键事实，用于后续内容创作的参考。")

    lines.append("")
    lines.append("【原文】")
    lines.append(text[:10000])  # 防止超长
    lines.append("")
    lines.append("【输出格式】严格 JSON：")
    lines.append("""```json
{
  "facts": [
    "事实1：具体描述",
    "事实2：具体描述"
  ],
  "key_entities": ["实体1", "实体2"],
  "timeline": ["时间点1: 事件描述", "时间点2: 事件描述"]
}
```""")
    return "\n".join(lines)


async def extract_facts_from_user_text(
    text: str,
    task_type: str = "general",
    provider: Optional[str] = None,
) -> Optional[str]:
    """从用户文本中提取事实，返回格式化的事实素材包文本。

    Args:
        text: 用户提供的原始文本（文件内容/链接内容/直接输入）
        task_type: 任务类型（continuation/polish/general）
        provider: LLM provider，默认 DeepSeek

    Returns:
        格式化的事实素材包文本，失败时返回 None
    """
    if not text or len(text.strip()) < 100:
        logger.info("[用户事实提取] 文本过短，跳过提取")
        return None

    client = get_llm_client(provider or "deepseek")
    prompt = _build_extraction_prompt(text, task_type)

    messages = [
        ChatMessage(role="system", content=EXTRACTION_SYSTEM_PROMPT),
        ChatMessage(role="user", content=prompt),
    ]

    try:
        resp = await client.chat(
            messages=messages,
            temperature=0.1,
            max_tokens=2000,
            json_mode=True,
        )
        parsed = parse_json_loose(resp.text)
        if not parsed:
            logger.warning("[用户事实提取] JSON 解析失败")
            return None

        facts = parsed.get("facts", [])
        entities = parsed.get("key_entities", [])
        timeline = parsed.get("timeline", [])

        if not facts and not entities:
            logger.info("[用户事实提取] 未提取到具体事实")
            return None

        # 格式化为素材包文本
        lines = []
        lines.append("【原文事实素材】（从用户提供的原文中提取）")
        lines.append("")

        if facts:
            lines.append("--- 关键事实 ---")
            for f in facts:
                lines.append(f"  · {f}")
            lines.append("")

        if timeline:
            lines.append("--- 时间线 ---")
            for t in timeline:
                lines.append(f"  · {t}")
            lines.append("")

        if entities:
            lines.append(f"--- 关键实体 --- {', '.join(entities)}")
            lines.append("")

        if task_type == "continuation":
            lines.append("【续写约束】")
            lines.append("- 续写内容中出现的任何具体事实，必须能在以上素材中找到来源")
            lines.append("- 如果要引入新的具体信息，必须是通用常识（如'Python 是编程语言'），不能编造具体数据")
            lines.append("- 保持原文中提到的数字、人名、产品名完全一致，不要改写")
        elif task_type == "polish":
            lines.append("【润色约束】")
            lines.append("- 改写后的内容必须保留以上所有事实，不能遗漏或篡改")
            lines.append("- 数字、日期、人名、产品名必须与原文完全一致")
            lines.append("- 不能在改写中引入原文没有的具体数据")

        result = "\n".join(lines)
        logger.info(f"[用户事实提取] 提取完成: {len(facts)} 条事实, {len(entities)} 个实体")
        return result

    except Exception as e:
        logger.error(f"[用户事实提取] 提取失败: {e}")
        return None

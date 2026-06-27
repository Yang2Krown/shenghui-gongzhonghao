"""正文续写服务 - 分析已写内容，生成自然收尾的续写方案。"""

import logging
from typing import Optional

from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位资深的公众号内容编辑，擅长分析文章脉络并给出自然流畅的续写方案。

你的核心能力是：
1. 精准把握文章的主题走向和情感基调
2. 找到文章最自然的"收束点"，而不是硬性总结
3. 续写要水到渠成，让读者觉得"就是这样"
4. 结尾要有力但不生硬，升华但不说教

你绝不会：
- 堆砌空洞的"总之"、"综上"、"总而言之"
- 硬生生拔高主题
- 重复前文已经说过的观点
- 用模板化的语言收尾"""


async def analyze_and_continue(content: str, preference: str = "", provider: Optional[str] = None) -> dict:
    """
    分析文章内容脉络，生成多个自然收尾的续写方案。
    
    Returns:
        {
            "analysis": {
                "main_theme": "...",
                "writing_style": "...",
                "logical_flow": "...",
                "emotional_tone": "..."
            },
            "plans": [
                {
                    "approach": "方案名称",
                    "description": "一句话说明",
                    "transition": "衔接过渡段",
                    "content": "续写正文",
                    "key_points": ["要点1", "要点2"]
                },
                ...
            ]
        }
    """
    client = get_llm_client(provider)

    # Phase 0: 从事实中提取素材包，降低续写幻觉
    source_material = None
    try:
        from app.utils.user_source_extractor import extract_facts_from_user_text
        source_material = await extract_facts_from_user_text(content, task_type="continuation", provider=provider)
    except Exception as e:
        logger.warning(f"[续写] 事实提取失败（不影响主流程）: {e}")

    preference_block = ""
    if preference.strip():
        preference_block = f"\n\n【用户偏好】\n{preference.strip()}"

    # 事实素材块（如果有）
    material_block = ""
    if source_material:
        material_block = f"\n\n{source_material}\n"

    prompt = f"""请分析以下已写好的文章正文，然后给出 3 个不同的续写收尾方案。

【已写正文】
{content[:6000]}
{preference_block}
{material_block}

【要求】
1. 先分析文章的内容脉络（核心主题、写作风格、逻辑走向、情感基调）
2. 然后给出 3 个不同风格的续写方案，每个方案包括：
   - approach: 方案名称（如"金句收尾"、"呼应开头"、"行动号召"等）
   - description: 一句话说明这个方案的特点
   - transition: 从正文最后一段自然过渡到续写的衔接段落（1-2句）
   - content: 续写的正文内容（200-400字）
   - key_points: 续写中的关键要点（2-3个）

3. 续写必须做到：
   - 与原文风格保持一致
   - 过渡自然，不能有"总之"、"综上"等生硬转折
   - 升华主题但不说教
   - 给读者留下深刻印象

4. 【事实约束 · 最高优先级】
   - 续写中涉及的具体事实（数字、日期、人名、产品名）必须与原文一致
   - 禁止在续写中编造原文没有的具体数据或事件
   - 如果「原文事实素材」中列出了关键事实，续写中引用时必须保持一致

请严格按照以下 JSON 格式输出：

{{
  "analysis": {{
    "main_theme": "核心主题",
    "writing_style": "写作风格",
    "logical_flow": "逻辑走向",
    "emotional_tone": "情感基调"
  }},
  "plans": [
    {{
      "approach": "方案名称",
      "description": "一句话说明",
      "transition": "衔接过渡段",
      "content": "续写正文",
      "key_points": ["要点1", "要点2"]
    }},
    {{
      "approach": "方案名称",
      "description": "一句话说明",
      "transition": "衔接过渡段",
      "content": "续写正文",
      "key_points": ["要点1", "要点2"]
    }},
    {{
      "approach": "方案名称",
      "description": "一句话说明",
      "transition": "衔接过渡段",
      "content": "续写正文",
      "key_points": ["要点1", "要点2"]
    }}
  ]
}}"""

    messages = [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(role="user", content=prompt),
    ]

    result = await client.chat(messages=messages, temperature=0.7, json_mode=True)
    response = result.text or ""

    parsed = parse_json_loose(response)
    if parsed is not None:
        return parsed

    import json
    try:
        return json.loads(response)
    except (json.JSONDecodeError, TypeError):
        logger.error(f"续写结果 JSON 解析失败: {response[:500]}")
        return {"analysis": {}, "plans": []}

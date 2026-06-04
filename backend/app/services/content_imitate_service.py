"""
内容仿写服务 - 学习参考内容的结构与语感，创作原创内容
"""
import logging
from typing import Optional, Dict, Any

from app.services.llm.llm_client import get_llm_client, ChatMessage

logger = logging.getLogger(__name__)


# 仿写系统提示词
IMITATE_SYSTEM_PROMPT = """你是一个专业的文案创作专家。你需要分析一篇参考内容的风格特点，然后基于这些特点创作一篇全新的原创内容。

## 核心原则

1. **学习风格**：分析参考内容的语言风格、句式结构、情感表达方式
2. **保持结构**：参考内容的段落结构、节奏感、信息组织方式
3. **原创内容**：基于学习到的风格特点，创作全新的内容，不是简单改写

## 分析维度

你需要从参考内容中学习以下维度：

### 语言风格
- 用词特点（正式/口语、简洁/详细、专业/通俗）
- 句式特点（长句/短句、疑问句/陈述句、主动/被动）
- 语气特点（理性/感性、客观/主观、严肃/轻松）

### 结构特点
- 段落数量和长度
- 信息组织方式（递进/并列/对比）
- 开头和结尾的特点

### 情感表达
- 情感基调（积极/中立/批判）
- 情感强度
- 表达方式（直接/含蓄）

## 输出要求

1. **标题**：根据学习到的风格特点，创作一个吸引人的标题
2. **正文**：基于学习到的风格特点，创作一篇 300-800 字的原创内容
3. **标签**：生成 3-5 个适合内容的标签

## 输出格式

请严格按照以下格式输出：

【标题】
[创作的标题]

【正文】
[创作的原创内容]

【标签】
#[标签1] #[标签2] #[标签3]

## 特别注意

- 保持原创性，不要复制或抄袭参考内容
- 学习风格特点，而不是具体内容
- 创作的内容要有自己的观点和见解
- 语言要自然流畅，符合学习到的风格特点
"""


async def imitate_content(
    reference_content: str,
    reference_title: Optional[str] = None,
    extra_requirements: Optional[str] = None,
) -> Dict[str, Any]:
    """
    学习参考内容的风格，创作原创内容

    Args:
        reference_content: 参考内容
        reference_title: 参考内容标题（可选）
        extra_requirements: 额外要求（可选）

    Returns:
        {title, content, tags}
    """
    try:
        # 构建用户消息
        user_message = "请分析以下参考内容的风格特点，然后基于这些特点创作一篇全新的原创内容：\n\n"

        if reference_title:
            user_message += f"参考内容标题：{reference_title}\n\n"

        user_message += f"参考内容：\n{reference_content}\n\n"

        if extra_requirements:
            user_message += f"额外要求：\n{extra_requirements}"

        # 调用 LLM
        llm = get_llm_client()
        messages = [
            ChatMessage(role="system", content=IMITATE_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_message),
        ]

        response = await llm.chat(messages, temperature=0.8, max_tokens=2000)
        result_text = response.text

        # 解析输出
        parsed = _parse_imitate_output(result_text)

        return {
            "success": True,
            "data": parsed,
        }

    except Exception as e:
        logger.error(f"内容仿写失败: {e}")
        return {"success": False, "error": str(e)}


def _parse_imitate_output(text: str) -> Dict[str, Any]:
    """解析仿写输出"""
    result = {
        "title": "",
        "content": "",
        "tags": [],
    }

    lines = text.strip().split("\n")
    current_section = None
    content_lines = []

    for line in lines:
        line_stripped = line.strip()

        if line_stripped.startswith("【标题】"):
            current_section = "title"
        elif line_stripped.startswith("【正文】"):
            current_section = "content"
            content_lines = []
        elif line_stripped.startswith("【标签】"):
            current_section = "tags"
        elif line_stripped.startswith("【"):
            current_section = None
        else:
            if current_section == "title" and line_stripped:
                result["title"] = line_stripped
                current_section = None
            elif current_section == "content":
                content_lines.append(line)
            elif current_section == "tags" and line_stripped:
                import re
                tags = re.findall(r"#([^\s#]+)", line_stripped)
                result["tags"] = tags

    result["content"] = "\n".join(content_lines).strip()

    return result

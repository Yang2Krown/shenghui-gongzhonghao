"""
内容转写服务 - 支持多平台间的内容风格转换
支持的平台：公众号、小红书、抖音、知乎
"""
import logging
from typing import Optional, Dict, Any

from app.services.llm.llm_client import get_llm_client, ChatMessage

logger = logging.getLogger(__name__)


# 平台风格指南
PLATFORM_GUIDES = {
    "wechat": {
        "name": "公众号",
        "style": """
## 公众号风格指南

### 语言风格
- 正式但不失亲和力，像在跟读者聊天
- 可以使用第一人称，拉近与读者的距离
- 适当使用比喻和类比，让抽象概念更易理解
- 段落之间有逻辑过渡，整体结构清晰

### 排版特点
- 标题：通常15-25字，可以包含数字、疑问句式
- 正文：分段清晰，每段3-5句话
- 可以使用小标题分割内容
- 适当使用加粗强调重点
- 结尾通常有总结或呼吁行动

### 内容限制
- 字数：通常1000-3000字
- 可以包含深度分析和详细论证
- 适合长内容、干货分享、观点输出
""",
    },
    "xhs": {
        "name": "小红书",
        "style": """
## 小红书风格指南

### 语言风格
- 口语化、朋友聊天式，完全口语化
- 使用第一人称，分享真实体验
- 适当使用网络流行语，但要自然
- 带有个人情感和真实反应

### 排版特点
- 标题：15字以内，包含1-2个emoji
- 正文：200-500字，分段短小精悍
- 使用emoji分隔段落
- 句子简短，节奏明快
- 结尾通常有互动引导

### 内容限制
- 严禁使用："谁懂啊"、"集美们"、"绝绝子"、"YYDS"、"OMG"
- 避免过多感叹号（全文不超过5个）
- emoji全文3-5个
- 需要包含具体时间、场景细节、心理活动

### 禁用词汇
- "宝子们"、"冲冲冲"、"必囤"
- 过度使用"真的"、"超级"、"巨"等程度词
""",
    },
    "douyin": {
        "name": "抖音",
        "style": """
## 抖音风格指南

### 语言风格
- 简洁直接，开门见山
- 口语化表达，像在跟朋友说话
- 情绪表达直接，可以有夸张
- 节奏快，信息密度高

### 排版特点
- 标题：通常10-20字，可以有悬念、疑问
- 正文：通常较短，100-300字
- 分段简短，每段1-2句话
- 适合快节奏内容消费

### 内容限制
- 适合短视频脚本、生活分享、热点评论
- 强调即时性和时效性
- 可以使用网络热梗
""",
    },
    "zhihu": {
        "name": "知乎",
        "style": """
## 知乎风格指南

### 语言风格
- 专业、理性、有深度
- 可以使用专业术语，但要解释清楚
- 逻辑严密，论证充分
- 客观中立，多角度分析

### 排版特点
- 标题：通常是问题或观点陈述
- 正文：结构清晰，有引言、论证、结论
- 可以使用列表、表格等格式
- 引用数据和来源增加可信度

### 内容限制
- 适合深度分析、专业知识分享
- 字数：通常500-2000字
- 强调逻辑性和专业性
- 可以包含个人观点，但要有理有据
""",
    },
}


# 转写系统提示词模板
TRANSFORM_SYSTEM_PROMPT = """你是一个专业的多平台内容转写专家。你需要将内容从一个平台的风格转换成另一个平台的风格。

## 核心原则

1. **保留核心信息**：原文的核心观点、数据、事实必须保留
2. **转换表达方式**：根据目标平台的特点，调整语言风格、排版、结构
3. **适配平台调性**：符合目标平台用户的内容消费习惯

## 源平台风格

{source_guide}

## 目标平台风格

{target_guide}

## 转写要求

1. **标题**：根据目标平台的标题风格重新创作
2. **正文**：根据目标平台的语言风格和排版特点重新组织内容
3. **标签**：生成适合目标平台的标签（3-5个）

## 输出格式

请严格按照以下格式输出：

【标题】
[转写后的标题]

【正文】
[转写后的正文内容]

【标签】
#[标签1] #[标签2] #[标签3]

## 特别注意

- 不要简单地搬运内容，要真正转换风格
- 保持原文的核心信息不变
- 符合目标平台的语言习惯和排版特点
- 标签要与内容相关，适合目标平台
"""


async def transform_content(
    content: str,
    source_platform: str,
    target_platform: str,
    original_title: Optional[str] = None,
    extra_requirements: Optional[str] = None,
) -> Dict[str, Any]:
    """
    将内容从一个平台转写成另一个平台的风格

    Args:
        content: 原文内容
        source_platform: 源平台 (wechat/xhs/douyin/zhihu)
        target_platform: 目标平台 (wechat/xhs)
        original_title: 原文章标题（可选）
        extra_requirements: 额外要求（可选）

    Returns:
        {title, content, tags}
    """
    try:
        # 验证平台参数
        if source_platform not in PLATFORM_GUIDES:
            return {"success": False, "error": f"不支持的源平台: {source_platform}"}
        if target_platform not in PLATFORM_GUIDES:
            return {"success": False, "error": f"不支持的目标平台: {target_platform}"}
        if source_platform == target_platform:
            return {"success": False, "error": "源平台和目标平台不能相同"}

        # 获取平台风格指南
        source_guide = PLATFORM_GUIDES[source_platform]["style"]
        target_guide = PLATFORM_GUIDES[target_platform]["style"]

        # 构建系统提示词
        system_prompt = TRANSFORM_SYSTEM_PROMPT.format(
            source_guide=source_guide,
            target_guide=target_guide,
        )

        # 构建用户消息
        user_message = f"请将以下{PLATFORM_GUIDES[source_platform]['name']}平台的内容，转写成{PLATFORM_GUIDES[target_platform]['name']}平台的风格：\n\n"
        if original_title:
            user_message += f"原标题：{original_title}\n\n"
        user_message += f"原文内容：\n{content}\n\n"

        if extra_requirements:
            user_message += f"额外要求：\n{extra_requirements}"

        # 调用 LLM
        llm = get_llm_client()
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_message),
        ]

        response = await llm.chat(messages, temperature=0.7, max_tokens=2000)
        result_text = response.text

        # 解析输出
        parsed = _parse_transform_output(result_text)

        return {
            "success": True,
            "data": parsed,
        }

    except Exception as e:
        logger.error(f"内容转写失败: {e}")
        return {"success": False, "error": str(e)}


def _parse_transform_output(text: str) -> Dict[str, Any]:
    """解析转写输出"""
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

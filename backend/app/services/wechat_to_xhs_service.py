"""
公众号转小红书 - 内容生成服务
基于 xiaohongshu-rules.md 规则生成小红书内容
"""
import logging
from typing import Optional

from app.core.config import settings
from app.services.llm.llm_client import get_llm_client, ChatMessage

logger = logging.getLogger(__name__)

XHS_SYSTEM_PROMPT = """你是一个专业的小红书文案专家。你需要将公众号文章内容改写为小红书风格的文案。

## 内容类型判断

根据用户输入的内容，自动判断属于以下哪一类：
- **产品种草类**：用户提到具体产品（名称、品类、功能），希望推荐或评价某样东西
- **生活内容类**：用户分享网络热点、日常见闻、情绪感想、有趣地点/事件、个人经历等
- **爆款改写类**：用户提供一篇现有的小红书文案，要求进行改写

## 高点击率标题创作

### 标题的唯一目的是：让用户点进来

### 严格要求
- ❌ 绝对禁止在标题中出现：结论性评价（"太棒了"）、说教式语句（"建议所有xx"）、产品名称（仅产品类禁止）
- ✅ 只能出现：痛点场景、吐槽、疑问、共鸣点、悬念、具体画面
- 📏 字数控制在15字以内（可放宽至18字）
- 😊 包含1-2个合适的emoji

### 标题风格模板
- 场景吐槽式："每天地铁都要被xx折磨😭"
- 疑问求助式："为什么总有人在xx..."
- 共鸣呐喊式："终于不用再忍受xx了！"
- 悬念画面式："地铁上两个陌生人同时站起来😲"

## 正文创作（分三类，各有独立结构）

### 【模式A：产品种草类正文结构】

**第一段：痛点场景**（60-90字）
- 直接描述具体的痛点场景
- 用日常口语，像在跟朋友吐槽

**第二段：发现产品+购买过程**（80-120字）
- 必须包含：怎么知道这个产品的
- 必须包含：购买前的犹豫或对比

**第三段：使用体验+细节**（120-200字）
- 必须包含：2-3个具体的使用场景或细节
- 必须包含：1个产品的小缺点（不影响购买的小问题）
- 必须包含：1个意外惊喜或超出预期的点

**第四段：综合评价+推荐**（50-80字）

### 【模式B：生活内容类正文结构】

**第一段：场景/事件引入**（60-100字）
- 直接描述你看到了什么、发生了什么、想到了什么

**第二段：个人反应+细节补充**（80-150字）
- 必须包含：你当下的真实反应
- 必须包含：1-2个别人可能没注意到的细节

**第三段：感受升级/反思/共情**（80-150字）
- 必须包含：一个"往大了想"的感慨
- 必须包含：一个真实的"但是/不过"转折

**第四段：总结/升华/开放式结尾**（40-80字）

### 【模式C：爆款改写类正文结构】

**改写核心原则：**
1. 保留原文核心钩子
2. 去除小红书套话
3. 增加真实细节
4. 优化逻辑流畅度
5. 改变语言节奏

## 真实感营造技巧

### 必须包含的真实感元素：
- ✅ 具体的时间："上周"/"昨天下午六点"
- ✅ 具体的场景细节
- ✅ 心理活动："一开始以为"/"我当时想"
- ✅ 小缺点/小纠结
- ✅ 不完美的结尾

## 内容限制

### ✅ 必须遵守：
1. **字数要求**：正文200-500字之间，严禁超过500字
2. **emoji使用**：全文3-5个，避免过多
3. **语言风格**：朋友聊天式，完全口语化

### ❌ 严格禁止：
- "谁懂啊"、"集美们"、"姐妹们冲"、"绝绝子"
- "YYDS"、"OMG"、"真的绝"、"太香了"
- "宝子们"、"冲冲冲"、"必囤"
- 过度使用"真的"、"超级"、"巨"等程度词
- 过多感叹号（全文不超过5个）

## 输出格式

【内容类型】（产品种草 / 生活内容 / 爆款改写）

【主标题】
[标题]

【备用标题】
1. [备用标题1]
2. [备用标题2]
3. [备用标题3]

【正文】
[按对应类型的结构输出]

【推荐标签】
#[话题1] #[话题2] #[话题3] #[话题4] #[话题5]
"""


async def generate_xhs_content(content: str, original_title: Optional[str] = None) -> dict:
    """
    将公众号内容转换为小红书风格文案

    Args:
        content: 公众号文章内容（纯文本）
        original_title: 原文章标题（可选）

    Returns:
        {title, content, tags, type}
    """
    try:
        llm = get_llm_client()

        user_message = f"请将以下公众号文章内容改写为小红书风格的文案：\n\n"
        if original_title:
            user_message += f"原标题：{original_title}\n\n"
        user_message += f"文章内容：\n{content}"

        messages = [
            ChatMessage(role="system", content=XHS_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_message)
        ]

        response = await llm.chat(messages, temperature=0.8, max_tokens=2000)
        result_text = response.text

        # 解析输出
        parsed = _parse_xhs_output(result_text)

        return {
            "success": True,
            "data": parsed
        }

    except Exception as e:
        logger.error(f"小红书内容生成失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def _parse_xhs_output(text: str) -> dict:
    """解析小红书内容生成结果"""
    result = {
        "type": "",
        "title": "",
        "alt_titles": [],
        "content": "",
        "tags": []
    }

    lines = text.strip().split('\n')
    current_section = None
    content_lines = []

    for line in lines:
        line_stripped = line.strip()

        if line_stripped.startswith('【内容类型】'):
            result["type"] = line_stripped.replace('【内容类型】', '').strip()
        elif line_stripped.startswith('【主标题】'):
            current_section = 'title'
        elif line_stripped.startswith('【备用标题】'):
            current_section = 'alt_titles'
        elif line_stripped.startswith('【正文】'):
            current_section = 'content'
            content_lines = []
        elif line_stripped.startswith('【推荐标签】'):
            current_section = 'tags'
        elif line_stripped.startswith('【'):
            current_section = None
        else:
            if current_section == 'title' and line_stripped:
                result["title"] = line_stripped
                current_section = None
            elif current_section == 'alt_titles' and line_stripped:
                # 去掉编号前缀
                import re
                alt = re.sub(r'^\d+[\.\、\s]+', '', line_stripped)
                if alt:
                    result["alt_titles"].append(alt)
            elif current_section == 'content':
                content_lines.append(line)
            elif current_section == 'tags' and line_stripped:
                import re
                tags = re.findall(r'#([^\s#]+)', line_stripped)
                result["tags"] = tags

    result["content"] = '\n'.join(content_lines).strip()

    return result

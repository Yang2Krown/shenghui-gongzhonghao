"""商业分类服务：自动归类甲方(品牌方)和功能方向。

检测出商单后，通过规则匹配 + LLM 兜底，给每篇商单打上：
- commercial_brand: 甲方/品牌方
- commercial_category: 功能方向
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.services.llm.llm_client import ChatMessage, get_llm_client

logger = logging.getLogger(__name__)


INVALID_COMMERCIAL_LABELS = {
    "无法判断", "未识别", "未知", "不明确", "无", "其他",
    "none", "null", "n/a", "unknown",
}


def normalize_commercial_label(value: Any) -> str:
    """Turn model placeholders into an empty value before storage/display."""
    text = str(value or "").strip()
    if text.lower() in INVALID_COMMERCIAL_LABELS:
        return ""
    return text[:100]


# ── 甲方(品牌方)映射 ──────────────────────────────────────────
# key: 归一化品牌名  value: 匹配关键词列表（大小写不敏感）
BRAND_KEYWORDS: Dict[str, List[str]] = {
    "OpenAI": [
        "openai", "chatgpt", "gpt-4", "gpt-3", "gpt4", "gpt3",
        "dall-e", "dall·e", "sora", "whisper", "o1", "o3", "codex",
    ],
    "Microsoft": [
        "microsoft", "微软", "copilot", "github copilot", "azure",
    ],
    "Meta": [
        "meta", "facebook", "llama",
    ],
    "字节跳动": [
        "字节", "byte", "豆包", "doubao", "扣子", "coze", "飞书",
        "feishu", "lark", "火山引擎", "剪映",
    ],
    "腾讯": [
        "腾讯", "tencent", "元宝", "混元", "微信", "wechat",
        "marvis", "miora", "workbuddy", "qclaw",
    ],
    "阿里巴巴": [
        "阿里", "alibaba", "通义", "qwen", "钉钉", "dingtalk",
        "夸克",
    ],
    "百度": [
        "百度", "baidu", "文心", "ernie", "千帆",
    ],
    "智谱AI": [
        "智谱", "zhipu", "chatglm", "glm-", "清言",
    ],
    "科大讯飞": [
        "讯飞", "iflytek", "星火", "讯飞星辰",
    ],
    "DeepSeek": [
        "deepseek", "深度求索",
    ],
    "月之暗面": [
        "月之暗面", "moonshot", "kimi",
    ],
    "零一万物": [
        "零一万物", "01.ai", "01ai", "yi-",
    ],
    "MiniMax": [
        "minimax", "海螺", "海螺ai",
    ],
    "Apple": [
        "apple", "苹果", "apple intelligence",
    ],
}


# ── 功能方向映射 ──────────────────────────────────────────────
# key: 归一化分类名  value: 匹配关键词列表
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "编程开发": [
        "编程", "代码", "coding", "code", "开发", "developer",
        "ide", "vscode", "github", "copilot", "cursor",
        "debug", "编译", "框架", "api", "sdk",
        "replit", "codex", "devin", "aider",
    ],
    "内容创作": [
        "写作", "创作", "文案", "文章", "博客", "小说",
        "writing", "content", "copywriting", "editor",
        "笔记", "notion", "飞书文档",
    ],
    "图像生成": [
        "图片生成", "画图", "绘图", "生图", "插画",
        "image generation", "midjourney", "dall-e", "dall·e",
        "stable diffusion", "sd ", "comfyui", "flux",
        "设计", "海报",
    ],
    "视频制作": [
        "视频", "video", "剪辑", "短视频", "vlog",
        "sora", "runway", "pika", "可灵", "kling",
        "直播", "剪辑",
    ],
    "办公效率": [
        "办公", "效率", "协作", "协同", "项目管理",
        "表格", "excel", "ppt", "文档", "日程",
        "会议纪要", "自动化", "workflow",
    ],
    "数据分析": [
        "数据分析", "报表", "bi ", "可视化", "数据",
        "analytics", "dashboard", "图表",
    ],
    "AI平台": [
        "平台", "platform", "大模型", "llm", "模型",
        "agent", "智能体", "workflow", "低代码", "no-code",
        "api调用", "推理",
    ],
    "教育学习": [
        "学习", "教育", "课程", "培训", "考试",
        "学习助手", "辅导", "教学",
    ],
    "营销推广": [
        "营销", "推广", "获客", "投放", "seo",
        "社媒", "运营", "增长",
    ],
    "硬件产品": [
        "硬件", "设备", "手机", "电脑", "芯片",
        "gpu", "服务器", "机器人",
    ],
}


# ── 前端展示用的筛选维度元数据 ──────────────────────────────────
BRAND_DISPLAY_ORDER = [
    "字节跳动", "腾讯", "阿里巴巴", "百度", "OpenAI",
    "Microsoft", "Meta", "DeepSeek", "智谱AI",
    "月之暗面", "科大讯飞", "零一万物", "MiniMax",
]

CATEGORY_DISPLAY_ORDER = [
    "编程开发", "内容创作", "图像生成", "视频制作",
    "办公效率", "数据分析", "AI平台", "教育学习", "营销推广", "硬件产品", "其他",
]


@dataclass
class ClassificationResult:
    brand: str = ""
    category: str = ""


def classify_by_rules(title: str, content: str, product: str = "") -> ClassificationResult:
    """规则匹配：先按 product 精确匹配，再扫 title+content 关键词。"""
    text = f"{product} {title} {content[:2000]}".lower()

    brand = _match_brand(text, product)
    category = _match_category(text)

    return ClassificationResult(brand=brand, category=category)


def _match_brand(text: str, product: str = "") -> str:
    product_lower = (product or "").lower()

    # 精确匹配 product 字段
    for brand, keywords in BRAND_KEYWORDS.items():
        for kw in keywords:
            if product_lower and kw.lower() in product_lower:
                return brand

    # 扫全文关键词（取命中最多的）
    scores: Dict[str, int] = {}
    for brand, keywords in BRAND_KEYWORDS.items():
        for kw in keywords:
            count = text.count(kw.lower())
            if count > 0:
                scores[brand] = scores.get(brand, 0) + count

    if scores:
        return max(scores, key=scores.get)

    return ""


def _match_category(text: str) -> str:
    scores: Dict[str, int] = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            count = text.count(kw.lower())
            if count > 0:
                scores[cat] = scores.get(cat, 0) + count

    if scores:
        return max(scores, key=scores.get)

    return ""


# ── LLM 兜底分类 ──────────────────────────────────────────────

_CLASSIFY_PROMPT = """你是AI行业分析师。根据以下公众号文章信息，完成两个分类任务：

1. **甲方/品牌方**：提取文章实际推广产品所属的公司或品牌。优先使用正文出现的真实名称；
   常见规范名包括 {brands}，但不限于这些品牌。无法判断时必须输出空字符串，不要输出“无法判断”“未知”或“其他”。

2. **功能方向**：推广的产品主要解决什么场景需求？从以下选项中选一个最匹配的，无法归类则选"其他"：
   {categories}

重要：品牌可以是名单外的新品牌；不要把标题的普通短语误当品牌。如果文章与AI/科技产品无关，品牌输出空字符串。

只输出 JSON，不要输出其他内容：
{{"brand": "品牌名", "category": "功能方向"}}

文章标题：{title}
产品名：{product}
正文节选（前800字）：
{excerpt}"""


async def classify_by_llm(
    title: str,
    content: str,
    product: str = "",
) -> ClassificationResult:
    """LLM 分类兜底：规则无法匹配时使用。"""
    brands_str = ", ".join(BRAND_DISPLAY_ORDER)
    cats_str = ", ".join(CATEGORY_DISPLAY_ORDER) + ", 其他"

    prompt = _CLASSIFY_PROMPT.format(
        brands=brands_str,
        categories=cats_str,
        title=title,
        product=product or "未识别",
        excerpt=(content or "")[:800],
    )

    try:
        client = get_llm_client("deepseek")
        result = await client.chat(
            [
                ChatMessage(role="system", content="你是严谨的AI行业分类分析师。"),
                ChatMessage(role="user", content=prompt),
            ],
            temperature=0.0,
            max_tokens=4096,
            json_mode=True,
        )
        parsed = result.parsed or {}
        brand = normalize_commercial_label(parsed.get("brand"))
        category = str(parsed.get("category") or "")

        # 品牌允许开放提取；功能方向仍使用固定维度。
        valid_cats = set(CATEGORY_DISPLAY_ORDER) | {"其他", ""}
        if category not in valid_cats:
            category = ""

        return ClassificationResult(brand=brand, category=category)

    except Exception as exc:
        logger.warning("商业分类 LLM 失败: %s", exc)
        return ClassificationResult()


async def classify_commercial(
    title: str,
    content: str,
    product: str = "",
) -> ClassificationResult:
    """先规则匹配，规则匹配不到再 LLM 兜底。"""
    rule_result = classify_by_rules(title, content, product)

    # 如果规则已经匹配到 brand 和 category，直接返回
    if rule_result.brand and rule_result.category:
        return rule_result

    # 部分命中：规则匹配到了 brand 但没 category（或反过来），只补全缺失的
    llm_result = await classify_by_llm(title, content, product)

    return ClassificationResult(
        brand=rule_result.brand or llm_result.brand,
        category=rule_result.category or llm_result.category,
    )

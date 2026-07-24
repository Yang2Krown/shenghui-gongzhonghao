"""小红书关键词/话题的 AI 相关性判定（轻量、确定性）。

供动态词生成（xhs_tasks）和话题总结（xhs_topics）共用。思路参照
services/preprocess/rules.py 的 is_ai_related：强 AI 关键词直接放行，
明显非 AI 主题（二次元/穿搭/美食/好视频扶持计划等）直接剔除，
短英文词（AI/LLM/GPT/MCP/agent/codex 等）用词边界匹配避免子串误命中。
"""
from __future__ import annotations

import re

# 强 AI 关键词：命中任一即判 AI 相关。中文用子串，短英文用词边界。
_STRONG_AI_KEYWORDS = [
    # 核心概念
    "AI", "人工智能", "AGI", "AIGC", "大模型", "LLM", "智能体", "agent",
    "机器学习", "深度学习", "具身智能", "MCP", "RAG", "embedding", "多模态",
    "扩散模型", "Transformer", "强化学习", "微调", "蒸馏", "提示词", "prompt",
    # 头部产品 / 公司
    "ChatGPT", "GPT", "Claude", "Gemini", "Grok", "Llama", "Sora",
    "OpenAI", "Anthropic", "DeepSeek", "Qwen", "Kimi", "Moonshot", "豆包",
    "Mistral", "xAI", "Cohere", "通义", "文心", "可灵", "即梦",
    # 编程 / Agent
    "Codex", "Cursor", "Copilot", "Devin", "Windsurf", "vibe coding",
    "Coding Agent", "MCP", "AI 编程", "AI编程",
    # 生成 / 多模态
    "Midjourney", "Stable Diffusion", "Runway", "Pika", "Luma", "Vidu",
    "文生图", "文生视频", "AI 绘画", "AI 视频", "AI 出图", "AI 搜索",
]

# 短英文关键词（含小写词）必须用词边界匹配，避免 "air"/"Brain"/"agent" 误命中。
_SHORT_EN_KEYWORDS = {"AI", "LLM", "GPT", "MCP", "A2A", "RAG", "AGI", "Sora", "agent", "codex", "prompt"}

# 明显非 AI 主题：命中即剔除（即使偶尔蹭到 AI 标签也不算）。
_NON_AI_KEYWORDS = [
    # 二次元 / 偶像 / 游戏
    "二次元", "动漫", "cosplay", "漫展", "番剧", "爱豆", "偶像", "饭圈",
    "kpop", "k-pop", "选秀", "应援", "原神", "崩坏", "王者荣耀", "手游", "二游",
    # 生活 / 美妆 / 美食 / 穿搭
    "穿搭", "美妆", "化妆", "护肤", "口红", "美甲", "美食", "探店", "旅游",
    "减肥", "健身", "瑜伽", "宠物", "养猫", "养狗", "婚礼", "婚纱", "恋爱", "相亲", "育儿",
    # 平台运营 / 流量扶持（非 AI 内容信号）
    "好视频扶持计划", "视频扶持", "流量扶持", "新人扶持", "涨粉", "官方活动",
    # 娱乐 / 影视
    "明星", "综艺", "电影", "票房", "追剧", "电视剧",
    # 金融 / 地产 / 汽车
    "股票", "基金", "房价", "楼市", "新能源车", "电动车", "车企",
]


def _keyword_hit(kw: str, text_raw: str, text_lower: str) -> bool:
    """单关键词命中：短英文用词边界，其他用 substring。"""
    if kw in _SHORT_EN_KEYWORDS:
        return bool(re.search(rf"\b{re.escape(kw)}\b", text_raw, re.IGNORECASE))
    return kw.lower() in text_lower


def is_ai_related(text: str) -> bool:
    """判断一段文本（关键词/话题名/标题拼接）是否与 AI 相关。

    规则：命中明显非 AI 主题且无强 AI 信号 → False；命中强 AI 关键词 → True；
    否则需弱信号（强词即弱词的超集）——这里要求至少 1 个强词，否则判非 AI。
    """
    raw = text or ""
    lower = raw.lower()
    has_strong = any(_keyword_hit(kw, raw, lower) for kw in _STRONG_AI_KEYWORDS)
    if not has_strong:
        # 无强 AI 信号时，命中明显非 AI 主题直接剔除；其余保守判非 AI。
        return False
    # 有强 AI 信号，但若主体明显是非 AI 主题（蹭 AI 标签），也剔除。
    if any(kw.lower() in lower for kw in _NON_AI_KEYWORDS):
        return False
    return True


def cluster_is_ai_related(titles_and_tags: list[str]) -> bool:
    """簇级兜底：簇内任一笔记标题/标签沾 AI 即保留；全不沾则剔除。"""
    return any(is_ai_related(t) for t in titles_and_tags)

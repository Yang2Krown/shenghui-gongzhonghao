"""纯规则字段计算：freshness / heat_score / low_fan_hit / direction。

设计文档 1.4 节字段。
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.models.info_cluster import FRESHNESS_24H, FRESHNESS_7D, FRESHNESS_30D, FRESHNESS_EXPIRED


def compute_freshness(published_at: Optional[datetime], *, now: Optional[datetime] = None) -> str:
    """根据发布时间打鲜度档位。"""
    if not published_at:
        return FRESHNESS_EXPIRED
    now = now or datetime.utcnow()
    delta = now - published_at
    if delta < timedelta(hours=24):
        return FRESHNESS_24H
    if delta < timedelta(days=7):
        return FRESHNESS_7D
    if delta < timedelta(days=30):
        return FRESHNESS_30D
    return FRESHNESS_EXPIRED


def compute_heat_score(
    *,
    source_weights: List[int],
    engagements: List[Dict[str, Any]],
    source_count: int,
) -> float:
    """簇级热度分（0-10）。综合：来源数 + 来源权重 + 互动数据。

    简单经验公式，后期可学习调参：
      heat = clamp(0.4 * (源数权重) + 0.3 * (互动归一化) + 0.3 * (源数加成), 0, 10)
    """
    if not source_weights and not engagements and source_count <= 0:
        return 0.0

    # 1) 来源权重均值 → 转 0-10（表 3 RSS 权重在 1-10）
    weight_part = sum(source_weights) / len(source_weights) if source_weights else 5.0

    # 2) 互动信号归一化（HN score 100+ = 满分；点赞 1000+ = 满分；按 log10）
    import math
    engagement_score = 0.0
    if engagements:
        peaks = []
        for e in engagements:
            score = e.get("score") or e.get("like") or e.get("like_count") or 0
            comments = e.get("comments") or e.get("comment_count") or 0
            raw = score + comments * 2
            if raw > 0:
                peaks.append(min(10.0, math.log10(raw + 1) * 3.0))
        engagement_score = max(peaks) if peaks else 0.0

    # 3) 多源加成（同主题 N 个源 → 越多越热，log 防爆）
    source_boost = min(10.0, math.log2(source_count + 1) * 3.0)

    heat = 0.4 * weight_part + 0.3 * engagement_score + 0.3 * source_boost
    return round(max(0.0, min(10.0, heat)), 2)


def compute_low_fan_hit(engagements: List[Dict[str, Any]]) -> bool:
    """低粉爆款标记（设计文档 1.4 节 + 表4）。

    P0 版本占位：判断单条互动是否远超均值。真正实现需要"账号近 10 条平均互动"，
    需要从 SourceAccount 维度建立基线，留待后续完善。
    """
    if not engagements:
        return False
    # 简化：任一条目互动总数（score + comments）> 200 视为"可能低粉爆款"
    for e in engagements:
        total = (e.get("score", 0) or 0) + (e.get("comments", 0) or 0) + (e.get("like", 0) or 0)
        if total > 200:
            return True
    return False


# ──────────────────────────────────────────────
# AI 相关性过滤
# ──────────────────────────────────────────────

# 宽泛的 AI/科技 关键词（中英文），命中任一即视为 AI 相关
AI_RELATED_KEYWORDS = [
    # 大模型 & 公司
    "AI", "人工智能", "大模型", "LLM", "GPT", "Claude", "Gemini", "Kimi", "Qwen", "DeepSeek",
    "Grok", "OpenAI", "Anthropic", "Google DeepMind", "Meta AI", "百度文心", "阿里通义",
    "智谱", "月之暗面", "MiniMax", "零一万物", "百川",
    # Coding Agent
    "Codex", "Cursor", "Copilot", "Claude Code", "vibe coding", "AI 编程", "coding agent",
    # Agent & 工作流
    "Agent", "MCP", "A2A", "agentic", "智能体", "工作流自动化",
    # AI 视频 & 出图
    "Sora", "Runway", "Vidu", "可灵", "即梦", "Pika", "Midjourney", "Stable Diffusion",
    "AI 视频", "视频生成", "AI 绘画", "出图",
    # AI 硬件 & 芯片
    "英伟达", "NVIDIA", "GPU", "TPU", "芯片", "算力", "H100", "B200", "Blackwell",
    # AI 应用
    "ChatGPT", "AI 搜索", "AI 助手", "AI 写作", "AI 翻译", "AI 编程工具",
    "具身智能", "机器人", "自动驾驶", "FSD",
    # 通用
    "机器学习", "深度学习", "神经网络", "transformer", "RAG", "向量数据库",
    "embedding", "微调", "fine-tune", "推理", "训练",
]


def is_ai_related(title: str, summary: str = "") -> bool:
    """判断内容是否与 AI 相关。标题或摘要命中任一关键词即返回 True。

    先排除明显非 AI 的主题（金融、地产、汽车、娱乐等），再检查 AI 关键词。
    """
    text = f"{title} {summary}".lower()

    # 排除：标题主体是非 AI 话题（即使偶尔提到 AI 也不算）
    NON_AI_PATTERNS = [
        # 金融/商业
        "ipo", "招股书", "上市", "融资", "估值", "市值", "股价", "财报", "营收",
        "投行", "券商", "基金", "私募", "风投", "vc", "收购", "并购",
        "巴菲特", "华尔街", "纳斯达克", "纽交所", "港股", "a股",
        # 地产/房产
        "租房", "房价", "楼市", "地产", "开发商", "土拍", "物业",
        # 汽车（非自动驾驶）
        "新能源车", "电动车", "车企", "造车", "4s店", "车展",
        "续航", "充电桩", "电池容量",
        # 娱乐/生活
        "明星", "综艺", "电影", "票房", "追星", "八卦",
        "美食", "旅游", "穿搭", "护肤",
        # 政治/军事
        "选举", "总统", "国会", "军事", "军演", "导弹",
        # 其他科技（非 AI）
        "5g", "6g", "光纤", "宽带", "运营商",
        "量子计算", "量子通信",
    ]

    # 如果标题核心词命中排除列表，且没有强 AI 关键词，视为非 AI
    # 简单策略：标题长度 > 10 字时，排除词出现在标题前半段视为主体
    title_lower = title.lower()
    has_strong_ai = any(kw.lower() in title_lower for kw in [
        "ai", "人工智能", "大模型", "llm", "gpt", "claude", "gemini",
        "openai", "anthropic", "deepseek", "agent", "codex", "cursor",
        "chatgpt", "机器学习", "深度学习", "具身智能",
    ])

    if not has_strong_ai:
        for pattern in NON_AI_PATTERNS:
            if pattern in title_lower:
                return False

    return any(kw.lower() in text for kw in AI_RELATED_KEYWORDS)


# 方向匹配：先用关键词字典，未来可换成 embedding 相似度匹配 SourceRegistry.direction_tags
DIRECTION_KEYWORDS = {
    "大模型": ["大模型", "GPT", "Claude", "Gemini", "Kimi", "Qwen", "DeepSeek", "Grok", "LLM"],
    "Coding Agent": ["Claude Code", "Codex", "Cursor", "Qoder", "vibecoding", "AI 编程", "code review", "coding agent"],
    "Agent 工作流": ["Agent", "MCP", "工作流", "skill", "routine", "agent memory"],
    "AI 视频/短剧": ["Runway", "Vidu", "可灵", "即梦", "Pika", "Luma", "短剧", "视频生成", "AI 视频"],
    "出图/设计": ["Midjourney", "出图", "Krea", "Recraft", "Figma", "海报", "封面", "Stable Diffusion"],
    "HTML/内容交付": ["html-anything", "Artifacts", "PPT", "网页化"],
    "Agent 基础设施": ["Memory", "成本", "Token", "推理优化", "agent infra"],
}


def detect_direction(title: str, summary: Optional[str] = None) -> Optional[str]:
    """从标题 + 摘要里关键词匹配方向。多个命中时返回命中关键词数最多的。"""
    text = (title or "") + " " + (summary or "")
    text_lower = text.lower()
    hits: Dict[str, int] = {}
    for direction, keywords in DIRECTION_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw.lower() in text_lower)
        if count > 0:
            hits[direction] = count
    if not hits:
        return None
    return max(hits, key=hits.get)

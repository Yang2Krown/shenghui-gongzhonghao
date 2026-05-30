"""纯规则字段计算：freshness / heat_score / low_fan_hit / direction。

设计文档 1.4 节字段。
"""

from datetime import datetime, timedelta
from app.core.timezone import utcnow
from typing import Any, Dict, List, Optional

from app.models.info_cluster import FRESHNESS_24H, FRESHNESS_7D, FRESHNESS_30D, FRESHNESS_EXPIRED


# 内容保鲜期：超过此天数的话题直接过滤掉（防止 2023 老古董出现）
MAX_CONTENT_AGE_DAYS = 90


def is_recent(published_at: Optional[datetime], *, max_days: int = MAX_CONTENT_AGE_DAYS,
              now: Optional[datetime] = None) -> bool:
    """判断内容是否在保鲜期内。

    - published_at 缺失视为新内容（保留，因为很多源不返回时间）
    - published_at 早于 now - max_days → False（淘汰）
    """
    if not published_at:
        return True
    now = now or utcnow()
    return (now - published_at) <= timedelta(days=max_days)


def compute_freshness(published_at: Optional[datetime], *, now: Optional[datetime] = None,
                      fallback_dt: Optional[datetime] = None) -> str:
    """根据发布时间打鲜度档位。

    当 published_at 为空时，使用 fallback_dt（通常是 cluster.created_at）作为替代，
    避免很多不返回发布时间的数据源（TopHub 等）被一刀切标为 expired。
    """
    dt = published_at or fallback_dt
    if not dt:
        return FRESHNESS_EXPIRED
    now = now or utcnow()
    delta = now - dt
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

# AI/科技 关键词（中英文）。原则：必须是 AI 专有词或强复合词，
# 避免单字"训练/推理/微调/机器人/Agent"等通用词误报（运动员训练、聊天机器人客服等）。
AI_RELATED_KEYWORDS = [
    # 大模型 & 公司 —— 专有名词
    "AI", "人工智能", "大模型", "LLM", "GPT", "Claude", "Gemini", "Kimi", "Qwen", "DeepSeek",
    "Grok", "OpenAI", "Anthropic", "Google DeepMind", "Meta AI", "百度文心", "阿里通义",
    "智谱", "月之暗面", "MiniMax", "零一万物", "百川",
    # Coding Agent
    "Codex", "Cursor", "Copilot", "Claude Code", "vibe coding", "AI 编程", "coding agent",
    "AI Coding", "AI 写代码", "AI 编辑器",
    # Agent & 工作流 —— 必须有"AI/智能/agentic"修饰
    "AI Agent", "Coding Agent", "MCP", "A2A", "agentic", "智能体", "工作流自动化",
    "Agent 工作流", "Agent Memory",
    # AI 视频 & 出图
    "Sora", "Runway", "Vidu", "可灵", "即梦", "Pika", "Midjourney", "Stable Diffusion",
    "AI 视频", "视频生成", "AI 绘画", "AI 出图", "文生图", "文生视频",
    # AI 硬件 & 芯片 —— 用专有型号 + AI 芯片复合词
    "英伟达", "NVIDIA", "H100", "B200", "Blackwell", "AI 芯片", "AI 算力",
    "GPU 算力", "TPU",
    # AI 应用
    "ChatGPT", "AI 搜索", "AI 助手", "AI 写作", "AI 翻译", "AI 编程工具",
    "具身智能", "AI 机器人", "人形机器人", "自动驾驶", "FSD",
    # AI 训练/推理 —— 复合词避免误报
    "机器学习", "深度学习", "神经网络", "transformer", "RAG", "向量数据库",
    "AI 推理", "模型推理", "模型训练", "AI 训练", "预训练",
    "模型微调", "LoRA 微调", "fine-tune", "embedding 模型",
]


# 短英文关键词（≤4 字母）必须用词边界匹配，避免子串误命中
# 比如 "AI" 不能匹配 URL 里的 "d59wc985ai2h1"
import re as _re
_SHORT_EN_KEYWORDS = {"AI", "LLM", "GPT", "MCP", "A2A", "TPU", "GPU", "RAG", "FSD", "AGI", "LoRA"}


def _keyword_hit(kw: str, text_raw: str, text_lower: str) -> bool:
    """单关键词命中检测：短英文用词边界，其他用 substring。"""
    if kw in _SHORT_EN_KEYWORDS:
        return bool(_re.search(rf"\b{_re.escape(kw)}\b", text_raw, _re.IGNORECASE))
    return kw.lower() in text_lower


_HASHTAG_RE = _re.compile(r"#[\w一-鿿]+")


def _strip_hashtags(text: str) -> str:
    """去掉 #xxx 标签 —— 标签里出现 AI 关键词不应让一条娱乐内容被判为 AI。"""
    return _HASHTAG_RE.sub(" ", text or "")


def is_ai_related(title: str, summary: str = "") -> bool:
    """判断内容是否与 AI 相关。标题或摘要命中任一关键词即返回 True。

    先排除明显非 AI 的主题（金融、地产、汽车、娱乐等），再检查 AI 关键词。
    注意：会剥掉 hashtag 再匹配——光在尾部标签里挂个 #ai 不算 AI 内容。
    """
    # 剥掉 hashtag 再做关键词匹配
    title_body = _strip_hashtags(title)
    summary_body = _strip_hashtags(summary)
    text_raw = f"{title_body} {summary_body}"
    text = text_raw.lower()

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
        "美食", "旅游", "穿搭", "护肤", "美妆", "化妆", "口红",
        "宠物", "养猫", "养狗", "铲屎官",
        "婚礼", "婚纱", "恋爱", "相亲", "婆媳", "亲子", "带娃", "育儿",
        # 偶像 / KPOP / 二次元
        "kpop", "k-pop", "爱豆", "偶像", "团综", "选秀", "出道",
        "饭圈", "应援", "打投", "ido", "嫂嫂", "老婆粉",
        # 游戏 / 模拟器 / 二游 / 手游
        "模拟器", "手游", "端游", "二游", "网游", "页游", "文游",
        "经纪人模拟", "恋爱模拟", "养成游戏", "乙游", "galgame",
        "原神", "崩坏", "明日方舟", "王者荣耀", "lol", "csgo",
        "steam", "switch", "playstation", "ns 游戏",
        # 健康/医疗/养生
        "猝死", "心梗", "癌症", "减肥", "健身", "瑜伽", "跑步", "马拉松",
        "运动员", "睡眠", "养生", "中医", "针灸",
        # 政治/军事/社会新闻
        "选举", "总统", "国会", "军事", "军演", "导弹",
        "裸辞", "辞职", "考研", "考公", "学区房",
        # 名人 / 突发事件
        "张雪峰", "周鸿祎", "罗永浩",  # 容易被借势但跟 AI 无关
        "猝死", "去世", "意外身亡", "讣告",
        # 其他科技（非 AI）
        "5g", "6g", "光纤", "宽带", "运营商",
        "量子计算", "量子通信",
    ]

    title_lower = title_body.lower()
    _strong_kws = [
        # 核心概念
        "AI", "人工智能", "AGI", "大模型", "LLM", "智能体", "Agent",
        "机器学习", "深度学习", "具身智能", "MCP", "RAG", "embedding",
        "扩散模型", "Transformer", "强化学习", "微调", "Fine-tune", "蒸馏",
        # 头部产品 / 公司
        "ChatGPT", "GPT", "Claude", "Gemini", "Grok", "Llama",
        "OpenAI", "Anthropic", "DeepSeek", "Qwen", "Kimi", "Moonshot",
        "Mistral", "xAI", "Cohere",
        # 编程类
        "Codex", "Cursor", "Copilot", "Devin", "Windsurf", "Qoder",
        "Coding Agent", "vibecoding", "vibe coding", "vibe 编程",
        # 多模态 / 生成
        "Sora", "Midjourney", "Stable Diffusion", "Runway", "Pika", "Luma",
        "可灵", "即梦", "Vidu", "ControlNet", "LoRA",
        # 其它
        "AIGC", "向量数据库", "AI 编程", "AI 视频", "AI 绘画",
    ]

    has_strong_ai_in_title = any(_keyword_hit(kw, title_body, title_lower) for kw in _strong_kws)
    # 标题没强 AI 信号且命中非 AI 主题（"模拟器""爱豆"等）→ 直接判非 AI
    if not has_strong_ai_in_title:
        for pattern in NON_AI_PATTERNS:
            if pattern in title_lower:
                return False

    # 剥 hashtag 后的全文里出现强 AI 关键词，就算 AI 相关——
    # 既能拦下"经纪人模拟器 #ai #deepseek"这种只在尾巴 hashtag 挂 AI 的，
    # 也能放过"用 ai 做了一个网页传输工具"这种正文里说 AI 的
    has_strong_ai_anywhere = any(_keyword_hit(kw, text_raw, text) for kw in _strong_kws)
    if has_strong_ai_anywhere:
        return True

    # 没强关键词时，要求弱关键词至少命中 2 个（更稳）
    weak_hits = sum(1 for kw in AI_RELATED_KEYWORDS if _keyword_hit(kw, text_raw, text))
    return weak_hits >= 2


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

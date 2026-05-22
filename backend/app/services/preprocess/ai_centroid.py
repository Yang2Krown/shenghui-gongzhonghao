"""AI 中心向量：一组核心概念文本的 embedding 平均，用于语义级别的 AI 相关度过滤。

工作流：
1. 首次调用 get_ai_centroid() 时，把 SEED_TEXTS 全部 embed → 取均值 → 缓存到 ai_centroid.npy
2. 后续直接读缓存
3. 过滤时算输入向量与 centroid 的 cosine 距离，> threshold 视为非 AI
"""

import json
import logging
import math
from pathlib import Path
from typing import List, Optional

from app.services.llm import embedding_service

logger = logging.getLogger(__name__)


CENTROID_FILE = Path(__file__).parent / "ai_centroid.json"

# 这些文本代表"AI 选题领域的中心"。涵盖：大模型/Coding Agent/AI 视频/出图/Agent 工作流/HTML 交付/AI 基建/AI 应用。
# 不要加财经、政治、社会新闻——会让中心向量发散。
SEED_TEXTS: List[str] = [
    # 大模型
    "OpenAI 发布 GPT-5 新一代大语言模型，推理能力大幅提升",
    "Anthropic 推出 Claude Sonnet 新版本，编程能力领先",
    "DeepSeek 开源大模型 V3，国内 AI 实验室开源浪潮",
    "Google Gemini 3.0 多模态模型评测，对比 Claude 和 GPT",
    # Coding Agent
    "Claude Code 实战教程：用 AI 编程提升 10 倍效率",
    "Cursor AI 编辑器入门，vibe coding 新工作流",
    "Codex Sandbox 让 AI Agent 在 Windows 上安全执行命令",
    "GitHub Copilot 升级，AI 代码审查自动化",
    # Agent / 工作流
    "MCP 协议详解：让 Claude 调用任意工具的标准",
    "Agent Memory 长期记忆架构，Skills 和 Routines 工作流",
    "智能体自动办公，从邮件总结到日程管理全自动",
    # AI 视频 / 出图
    "Runway Gen-4 视频生成模型，电影级 AI 短剧制作流",
    "可灵 / 即梦 / Vidu 中文 AI 视频对比评测",
    "Midjourney 提示词工程，AI 海报和封面设计实战",
    "Stable Diffusion 微调技巧，AI 出图工作流",
    # HTML / 内容交付
    "Claude Artifacts 输出可执行网页，AI 不只是写稿",
    "AI 生成 PPT 工作流，从大纲到设计自动化",
    # AI 基础设施
    "Token 优化和成本控制，企业部署 Agent 的算力账",
    "向量数据库 + RAG 检索增强生成，企业知识库实战",
    "AI 推理优化，从蒸馏到量化的工程实践",
    # AI 应用 / 产业
    "AI Agent 商业化，从开发者工具到企业 SaaS",
    "Anthropic / OpenAI 融资和上市，AI 商业版图",
    "英伟达 GPU 算力，AI 训练芯片的供需博弈",
]


def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(v: List[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def cosine_distance(a: List[float], b: List[float]) -> float:
    """返回 1 - cosine_similarity，范围 [0, 2]。0 = 完全相同方向，1 = 正交，2 = 完全相反。"""
    na, nb = _norm(a), _norm(b)
    if na == 0 or nb == 0:
        return 1.0
    sim = _dot(a, b) / (na * nb)
    return 1.0 - sim


async def build_ai_centroid(force: bool = False) -> List[float]:
    """构建并缓存 AI 中心向量。force=True 时强制重建。"""
    if CENTROID_FILE.exists() and not force:
        try:
            data = json.loads(CENTROID_FILE.read_text(encoding="utf-8"))
            vec = data.get("centroid")
            if isinstance(vec, list) and len(vec) > 0:
                logger.info(f"从缓存加载 AI centroid (dim={len(vec)})")
                return vec
        except Exception as e:
            logger.warning(f"加载 centroid 缓存失败，重新构建: {e}")

    logger.info(f"开始构建 AI centroid（{len(SEED_TEXTS)} 条种子文本）...")
    vectors = await embedding_service.embed_batch(SEED_TEXTS)
    valid = [v for v in vectors if v is not None]
    if not valid:
        raise RuntimeError("AI centroid 构建失败：所有 seed embed 都失败")

    dim = len(valid[0])
    centroid = [sum(v[i] for v in valid) / len(valid) for i in range(dim)]

    CENTROID_FILE.write_text(
        json.dumps({"centroid": centroid, "seed_count": len(valid), "dim": dim}, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"AI centroid 构建完成: dim={dim}, 有效种子={len(valid)}/{len(SEED_TEXTS)}")
    return centroid


# 缓存到模块级（首次调用时初始化）
_centroid_cache: Optional[List[float]] = None


async def get_ai_centroid() -> List[float]:
    global _centroid_cache
    if _centroid_cache is None:
        _centroid_cache = await build_ai_centroid()
    return _centroid_cache


def is_ai_semantically(embedding: List[float], centroid: List[float], threshold: float = 0.55) -> bool:
    """语义层 AI 判定：embedding 与 centroid 的 cosine 距离 < threshold 视为 AI。

    cosine 距离阈值经验值：
    - 0.40：非常严格（漏过率高，但精确）
    - 0.55：推荐，平衡漏过/误杀
    - 0.70：宽松（容易让非 AI 内容混进来）
    """
    return cosine_distance(embedding, centroid) < threshold

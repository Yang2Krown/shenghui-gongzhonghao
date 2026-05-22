"""LLM 富集：给 InfoCluster 打"信息类型 + 6 要素"。

对齐设计文档 1.4 节"要素"：主体 / 动作 / 对象 / 亮点 / 争议 / 数据。
单次 LLM 调用同时输出全部字段，按 cluster 粒度（簇内多个 RawInfo 摘要一起喂）。
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.info_cluster import (
    InfoCluster,
    INFO_TYPE_NEWS,
    INFO_TYPE_CASE,
    INFO_TYPE_OPINION,
    INFO_TYPE_TUTORIAL,
)
from app.models.raw_info import RawInfo
from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage

logger = logging.getLogger(__name__)


VALID_INFO_TYPES = {INFO_TYPE_NEWS, INFO_TYPE_CASE, INFO_TYPE_OPINION, INFO_TYPE_TUTORIAL}


SYSTEM_PROMPT = """你是一个内容信息抽取助手。给你一组来自多个来源的同主题资讯，你需要：

1. 判断这组信息属于哪种类型，**只能从以下 4 选 1**：
   - 资讯型：报道新发生的事件、产品发布、人事变动、数据公布
   - 实操案例型：具体的操作案例、Demo 演示、用户实操记录
   - 观点分享型：作者的观点、判断、争论、行业评论
   - 教程型：完整的步骤指引、how-to、教学内容

2. 抽取 6 个要素（不存在的字段输出空字符串）：
   - 主体：事件的核心人物 / 组织 / 产品名（如 OpenAI、Claude Code、某博主）
   - 动作：发生了什么动作（发布 / 更新 / 宣布 / 评测 / 翻车 / 演示）
   - 对象：动作的对象（新模型 / 新功能 / 某产品 / 某话题）
   - 亮点：最值得关注的细节（一句话）
   - 争议：是否存在争议点（一句话；没有就空字符串）
   - 数据：有没有具体数字 / 性能数据 / 价格数据（原文照抄关键数字）

**只输出严格 JSON**，格式：
{
  "info_type": "资讯型 | 实操案例型 | 观点分享型 | 教程型",
  "elements": {
    "主体": "...",
    "动作": "...",
    "对象": "...",
    "亮点": "...",
    "争议": "...",
    "数据": "..."
  }
}"""


def _build_user_prompt(cluster: InfoCluster, raws: List[RawInfo]) -> str:
    """把簇内 RawInfo 拼成 LLM 输入。"""
    lines = [f"【主题（候选标题）】{cluster.core_title}", "", "【来源资讯】"]
    # 最多 5 条，按 published_at 倒序
    sorted_raws = sorted(raws, key=lambda r: r.published_at or r.created_at or 0, reverse=True)
    for i, r in enumerate(sorted_raws[:5], 1):
        lines.append(f"\n[{i}] 标题：{r.title or ''}")
        if r.summary:
            lines.append(f"    摘要：{r.summary[:400]}")
        if r.author:
            lines.append(f"    作者：{r.author}")
    return "\n".join(lines)


async def enrich_cluster(
    db: AsyncSession,
    cluster: InfoCluster,
    *,
    llm_client=None,
) -> bool:
    """对单个簇调一次 LLM，写回 info_type + elements。返回是否成功。"""
    # 拉簇内 RawInfo
    raws = (await db.execute(
        select(RawInfo).where(RawInfo.info_cluster_id == cluster.id)
    )).scalars().all()
    if not raws:
        logger.warning(f"cluster {cluster.id} 没有关联 RawInfo，跳过 enrich")
        return False

    user_prompt = _build_user_prompt(cluster, raws)
    client = llm_client or get_llm_client()

    try:
        result = await client.chat(
            messages=[
                ChatMessage(role="system", content=SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_prompt),
            ],
            temperature=0.2,
            max_tokens=800,
            json_mode=True,
        )
    except Exception as e:
        logger.error(f"cluster {cluster.id} LLM 调用失败: {e}")
        return False

    parsed = result.parsed
    if not parsed:
        logger.warning(f"cluster {cluster.id} LLM 输出无法解析为 JSON")
        return False

    info_type = parsed.get("info_type", "").strip()
    if info_type not in VALID_INFO_TYPES:
        logger.warning(f"cluster {cluster.id} LLM 返回非法 info_type='{info_type}'")
        # 兜底归为资讯型，便于后续处理
        info_type = INFO_TYPE_NEWS

    elements = parsed.get("elements") or {}
    if not isinstance(elements, dict):
        elements = {}

    cluster.info_type = info_type
    cluster.elements = elements

    logger.info(
        f"cluster {cluster.id} enriched: type={info_type} usage={result.usage}"
    )
    return True


async def enrich_clusters(db: AsyncSession, clusters: List[InfoCluster]) -> int:
    """批量富集；按顺序调（DeepSeek 单 key 并发受限）。"""
    if not clusters:
        return 0
    client = get_llm_client()
    success = 0
    for c in clusters:
        ok = await enrich_cluster(db, c, llm_client=client)
        if ok:
            success += 1
    await db.flush()
    logger.info(f"enrich: {success}/{len(clusters)} 簇成功")
    return success

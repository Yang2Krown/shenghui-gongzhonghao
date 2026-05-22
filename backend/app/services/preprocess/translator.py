"""英文 → 中文翻译服务。

只翻译英文为主的 cluster，中文 cluster 不动。
DeepSeek 调用：批量传入多条，一次 LLM 调用翻译全部，省 token。
"""

import logging
import re
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.info_cluster import InfoCluster
from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose

logger = logging.getLogger(__name__)


CHINESE_RE = re.compile(r"[一-鿿]")


def is_english_dominant(text: str, threshold: float = 0.3) -> bool:
    """中文字符占比 < threshold 视为英文主导。空文本返回 False（无需翻译）。"""
    if not text or not text.strip():
        return False
    text = text.strip()
    chinese_chars = len(CHINESE_RE.findall(text))
    total_meaningful = sum(1 for ch in text if not ch.isspace())
    if total_meaningful == 0:
        return False
    return (chinese_chars / total_meaningful) < threshold


SYSTEM_PROMPT = """你是一个专业的科技 / AI 行业新闻标题翻译助手。

任务：把多条英文新闻标题或摘要翻译成简洁、地道、有传播感的中文。

规则：
1. 标题翻译要短，控制在 22 字内；保留产品名、公司名、人名的原文（如 Anthropic / Claude / Karpathy）
2. 摘要翻译可适当意译，保持信息密度；不超过原文 1.5 倍长度
3. 避免直译腔，按中文新闻标题的习惯改写
4. 输出严格 JSON，按输入顺序对应

输入格式：
[
  {"id": 1, "title": "...", "summary": "..."},
  ...
]

输出格式：
{
  "translations": [
    {"id": 1, "title_zh": "...", "summary_zh": "..."},
    ...
  ]
}

注意：summary 为空时 summary_zh 也输出空字符串。"""


async def translate_clusters(
    db: AsyncSession,
    clusters: List[InfoCluster],
    *,
    batch_size: int = 10,
) -> int:
    """批量翻译 cluster 列表。返回成功翻译的数量。"""
    if not clusters:
        return 0

    client = get_llm_client()
    total_translated = 0

    # 按 batch_size 切片，每批一次 LLM 调用
    for start in range(0, len(clusters), batch_size):
        batch = clusters[start : start + batch_size]
        # 构造输入：每条 cluster 一个 dict
        items = []
        for i, c in enumerate(batch):
            items.append({
                "id": i,
                "title": (c.core_title or "").strip(),
                "summary": (c.summary or "").strip()[:300],
            })

        user_msg = "请翻译以下条目：\n" + str(items).replace("'", '"')

        try:
            result = await client.chat(
                messages=[
                    ChatMessage(role="system", content=SYSTEM_PROMPT),
                    ChatMessage(role="user", content=user_msg),
                ],
                temperature=0.3,
                max_tokens=4000,
                json_mode=True,
            )
        except Exception as e:
            logger.error(f"翻译批次失败 (start={start}): {e}")
            continue

        parsed = result.parsed or parse_json_loose(result.text)
        if not parsed or "translations" not in parsed:
            logger.warning(f"翻译响应解析失败 (start={start}): {result.text[:200]}")
            continue

        trans_by_id = {t.get("id"): t for t in parsed["translations"] if isinstance(t, dict)}
        for i, c in enumerate(batch):
            t = trans_by_id.get(i)
            if not t:
                continue
            title_zh = (t.get("title_zh") or "").strip()
            summary_zh = (t.get("summary_zh") or "").strip()
            if title_zh:
                c.core_title_zh = title_zh[:500]
                total_translated += 1
            if summary_zh:
                c.summary_zh = summary_zh

    await db.flush()
    logger.info(f"翻译完成: {total_translated}/{len(clusters)}")
    return total_translated


async def translate_pending(db: AsyncSession, limit: Optional[int] = None) -> Dict[str, int]:
    """找出所有需要翻译但还没翻的英文 cluster，批量翻译。

    判定条件：core_title 英文主导 + core_title_zh 为空。
    """
    stmt = select(InfoCluster).where(InfoCluster.core_title_zh.is_(None))
    if limit:
        stmt = stmt.limit(limit)
    candidates = (await db.execute(stmt)).scalars().all()

    # 应用语言判定
    need_translate = [c for c in candidates if is_english_dominant(c.core_title or "")]
    logger.info(f"待翻译候选 {len(candidates)} → 英文主导 {len(need_translate)}")

    translated = await translate_clusters(db, need_translate)
    await db.commit()
    return {
        "candidates": len(candidates),
        "english_dominant": len(need_translate),
        "translated": translated,
    }

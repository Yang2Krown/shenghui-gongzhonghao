"""全局排序服务。

职责：跨簇去重、方向多样性约束、Top N 输出 → DailyTopicList。
不在选题挖掘 Agent 范围内，是下游脚本层。
"""

import logging
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session, joinedload

from app.db.session import SessionLocal
from app.models.topic_candidate import TopicCandidate
from app.models.daily_topic_list import DailyTopicList, DailyTopicListItem
from app.models.info_cluster import InfoCluster

logger = logging.getLogger(__name__)

# 方向多样性约束：每个方向最多占比
MAX_DIRECTION_RATIO = 0.4  # 最多 40% 来自同一方向
MIN_DIRECTIONS = 3  # 至少覆盖 3 个方向


def _deduplicate_by_title(candidates: List[TopicCandidate]) -> List[TopicCandidate]:
    """按标题相似度去重（简单实现：标题完全相同则去重）。"""
    seen_titles = set()
    unique = []
    for c in candidates:
        normalized = c.title.strip().lower()
        if normalized not in seen_titles:
            seen_titles.add(normalized)
            unique.append(c)
    return unique


def _deduplicate_by_cluster(candidates: List[TopicCandidate]) -> List[TopicCandidate]:
    """同簇去重：每个 InfoCluster 只保留得分最高的候选。"""
    cluster_best = {}
    for c in candidates:
        cid = c.info_cluster_id
        if cid not in cluster_best or c.weighted_score > cluster_best[cid].weighted_score:
            cluster_best[cid] = c
    return list(cluster_best.values())


def _enforce_direction_diversity(
    candidates: List[TopicCandidate],
    top_n: int,
) -> List[TopicCandidate]:
    """方向多样性约束：确保至少覆盖 MIN_DIRECTIONS 个方向，单方向不超过 MAX_DIRECTION_RATIO。"""
    if not candidates:
        return []

    # 按方向分组
    by_direction = {}
    for c in candidates:
        d = c.direction or "未分类"
        by_direction.setdefault(d, []).append(c)

    # 每个方向内部按分数排序
    for d in by_direction:
        by_direction[d].sort(key=lambda x: x.weighted_score or 0, reverse=True)

    max_per_direction = max(1, int(top_n * MAX_DIRECTION_RATIO))
    result = []
    used_directions = set()

    # 第一轮：每个方向取最高分的 1 个（确保方向覆盖）
    for d, items in by_direction.items():
        if items and len(result) < top_n:
            result.append(items.pop(0))
            used_directions.add(d)

    # 第二轮：按分数填充剩余名额，遵守单方向上限
    direction_counts = {d: 1 if d in used_directions else 0 for d in by_direction}
    remaining = []
    for d, items in by_direction.items():
        remaining.extend(items)
    remaining.sort(key=lambda x: x.weighted_score or 0, reverse=True)

    for c in remaining:
        if len(result) >= top_n:
            break
        d = c.direction or "未分类"
        if direction_counts.get(d, 0) < max_per_direction:
            result.append(c)
            direction_counts[d] = direction_counts.get(d, 0) + 1

    return result


def generate_daily_list(
    target_date: Optional[date] = None,
    top_n: int = 10,
) -> dict:
    """生成每日选题清单。

    Args:
        target_date: 目标日期，默认今天
        top_n: 取前 N 个

    Returns:
        {"list_id": int, "date": str, "count": int, "direction_distribution": dict}
    """
    db = SessionLocal()
    try:
        target = target_date or date.today()

        # 检查是否已生成
        existing = db.query(DailyTopicList).filter(DailyTopicList.list_date == target).first()
        if existing:
            logger.info(f"每日清单 {target} 已存在，跳过")
            return {"list_id": existing.id, "date": str(target), "status": "already_exists"}

        # 拉取所有 selected 候选，按分数倒序
        candidates = (
            db.query(TopicCandidate)
            .options(joinedload(TopicCandidate.info_cluster))
            .filter(TopicCandidate.verdict == "selected")
            .order_by(desc(TopicCandidate.weighted_score))
            .all()
        )

        if not candidates:
            logger.warning(f"没有 selected 候选，无法生成清单")
            return {"date": str(target), "count": 0, "status": "no_candidates"}

        # 去重
        candidates = _deduplicate_by_title(candidates)
        candidates = _deduplicate_by_cluster(candidates)

        # 方向多样性
        candidates = _enforce_direction_diversity(candidates, top_n)

        # 按分数排序取 Top N
        candidates.sort(key=lambda x: x.weighted_score or 0, reverse=True)
        top_candidates = candidates[:top_n]

        # 方向分布统计
        direction_dist = {}
        for c in top_candidates:
            d = c.direction or "未分类"
            direction_dist[d] = direction_dist.get(d, 0) + 1

        # 写入 DailyTopicList
        daily_list = DailyTopicList(
            list_date=target,
            top_n=top_n,
            items=[
                {
                    "candidate_id": c.id,
                    "rank": i + 1,
                    "title": c.title,
                    "direction": c.direction,
                    "score": c.weighted_score,
                    "verdict": c.verdict,
                }
                for i, c in enumerate(top_candidates)
            ],
            direction_distribution=direction_dist,
        )
        db.add(daily_list)
        db.flush()

        # 写入 DailyTopicListItem（normalized 表）
        for i, c in enumerate(top_candidates):
            db.add(DailyTopicListItem(
                list_id=daily_list.id,
                candidate_id=c.id,
                rank=i + 1,
                score_snapshot=c.weighted_score,
            ))

        db.commit()

        logger.info(f"每日清单 {target} 生成完成: {len(top_candidates)} 个选题")
        return {
            "list_id": daily_list.id,
            "date": str(target),
            "count": len(top_candidates),
            "direction_distribution": direction_dist,
        }

    except Exception as e:
        db.rollback()
        logger.exception(f"生成每日清单失败: {e}")
        raise
    finally:
        db.close()

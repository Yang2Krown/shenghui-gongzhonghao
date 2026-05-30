"""预处理 pipeline 主入口：RawInfo → InfoCluster。

流程：
1. 拉 RAW_STATE_PENDING 的 RawInfo（带 source / engagement 信息）
2. 批量 embed
3. 聚类（pgvector cosine）
4. 对被触达的簇调 LLM 富集（info_type + elements）
5. 算簇级 freshness / heat_score / direction / low_fan_hit
6. 标 RawInfo state=CLUSTERED
"""

import logging
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.info_cluster import InfoCluster
from app.models.raw_info import RawInfo, RAW_STATE_PENDING, RAW_STATE_SKIPPED
from app.models.source_registry import SourceRegistry
from app.services.preprocess.embedder import embed_raw_infos
from app.services.preprocess.clusterer import cluster_raw_batch
from app.services.preprocess.enricher import enrich_clusters
from app.services.preprocess.rules import (
    compute_freshness,
    compute_heat_score,
    compute_low_fan_hit,
    detect_direction,
    is_ai_related,
    is_recent,
)

logger = logging.getLogger(__name__)


class PreprocessPipeline:
    """主流程。"""

    DEFAULT_BATCH = 100

    async def run_batch(
        self,
        db: AsyncSession,
        *,
        limit: int = DEFAULT_BATCH,
    ) -> Dict[str, Any]:
        # 1. 拉待处理（join source 拿 weight，用于低权重跳过）
        stmt = (
            select(RawInfo)
            .options(selectinload(RawInfo.source))
            .where(RawInfo.state == RAW_STATE_PENDING)
            .order_by(RawInfo.created_at)
            .limit(limit)
        )
        raws = (await db.execute(stmt)).scalars().unique().all()
        if not raws:
            logger.info("preprocess: 无待处理 RawInfo")
            return {"pending": 0, "embedded": 0, "clusters_touched": 0, "enriched": 0}

        stats: Dict[str, Any] = {"pending": len(raws)}

        # 2a. 时效过滤：超过 90 天的老内容直接淘汰（防止 2023 古董出现）
        fresh_raws = []
        skipped_too_old = 0
        for r in raws:
            if is_recent(r.published_at):
                fresh_raws.append(r)
            else:
                r.state = RAW_STATE_SKIPPED
                skipped_too_old += 1
        stats["skipped_too_old"] = skipped_too_old
        if skipped_too_old:
            logger.info(f"preprocess: 跳过 {skipped_too_old} 条超过 90 天的老内容")

        # 2b. AI 相关性过滤：跳过非 AI 内容
        ai_related = []
        skipped_non_ai = 0
        for r in fresh_raws:
            if is_ai_related(r.title or "", r.summary or ""):
                ai_related.append(r)
            else:
                r.state = RAW_STATE_SKIPPED
                skipped_non_ai += 1
        if skipped_non_ai:
            logger.info(f"preprocess: 跳过 {skipped_non_ai} 条非 AI 内容")

        # 2c. 来源权重过滤：低权重来源（weight <= 2）跳过 embedding，节省成本
        #     仍保留这些 raw 的状态为 pending，后续可手动触发
        EMBED_MIN_WEIGHT = 2
        embeddable = []
        skipped_low_weight = 0
        for r in ai_related:
            src_weight = r.source.weight if r.source else None
            if src_weight is not None and src_weight <= EMBED_MIN_WEIGHT:
                skipped_low_weight += 1
                continue
            embeddable.append(r)
        if skipped_low_weight:
            logger.info(f"preprocess: 跳过 {skipped_low_weight} 条低权重来源（weight<={EMBED_MIN_WEIGHT}）")

        # 3. embed（只对通过权重过滤的 embeddable）
        stats["embedded"] = await embed_raw_infos(db, embeddable)
        stats["skipped_low_weight"] = skipped_low_weight

        # 3.5 Layer 3 语义过滤：用 ai_centroid 算与 AI 中心的 cosine 距离
        from app.services.preprocess.ai_centroid import get_ai_centroid, cosine_distance
        centroid = await get_ai_centroid()
        semantic_skipped = 0
        for r in embeddable:
            if r.embedding is None:
                continue
            if cosine_distance(list(r.embedding), centroid) >= 0.55:
                r.state = RAW_STATE_SKIPPED
                semantic_skipped += 1
        stats["skipped_by_semantic"] = semantic_skipped
        if semantic_skipped:
            logger.info(f"preprocess: 语义过滤跳过 {semantic_skipped} 条")

        # 4. 过滤掉 embed 失败的 + Layer 3 标 SKIPPED 的，进入聚类
        clusterable = [r for r in embeddable if r.embedding is not None and r.state != RAW_STATE_SKIPPED]
        clusters = await cluster_raw_batch(db, clusterable)
        stats["clusters_touched"] = len(clusters)

        # 4. LLM 富集（只对"还没挖掘"的簇——新建的 / 新合并的）
        to_enrich = [c for c in clusters if not c.mined]
        stats["enriched"] = await enrich_clusters(db, to_enrich)

        # 4.5 翻译：英文 cluster 自动翻成中文（只翻刚 enrich 过的新簇）
        from app.services.preprocess.translator import translate_clusters, is_english_dominant
        to_translate = [
            c for c in to_enrich
            if c.core_title_zh is None and is_english_dominant(c.core_title or "")
        ]
        stats["translated"] = await translate_clusters(db, to_translate) if to_translate else 0

        # 5. 规则字段（freshness / heat_score / direction / low_fan_hit）
        await self._apply_rules(db, clusters)

        await db.commit()
        logger.info(
            f"preprocess 完成: pending={stats['pending']} embedded={stats['embedded']} "
            f"clusters={stats['clusters_touched']} enriched={stats['enriched']}"
        )
        return stats

    async def _apply_rules(self, db: AsyncSession, clusters: List[InfoCluster]) -> None:
        """对触达的每个簇刷新规则字段。"""
        for cluster in clusters:
            # 拉簇内 raw_infos + 对应 source（一次性 join）
            raws = (await db.execute(
                select(RawInfo)
                .options(selectinload(RawInfo.source))
                .where(RawInfo.info_cluster_id == cluster.id)
            )).scalars().all()

            if not raws:
                continue

            # freshness：published_at 缺失时用 cluster.created_at 兜底
            cluster.freshness = compute_freshness(
                cluster.published_at, fallback_dt=cluster.created_at
            )

            # heat_score（所有来源平等，不按来源渠道/类型加分）
            engagements = [r.engagement or {} for r in raws]
            cluster.heat_score = compute_heat_score(
                engagements=engagements,
                source_count=cluster.source_count or len(raws),
            )

            # 低粉爆款
            cluster.low_fan_hit = compute_low_fan_hit(engagements)

            # direction（标题 + 摘要关键词匹配）
            if not cluster.direction:
                cluster.direction = detect_direction(cluster.core_title, cluster.summary)

            # AI 相关性：原文 + 中文翻译都喂进去判一遍，结果落库给列表 API 用
            _title = " ".join(filter(None, [cluster.core_title, cluster.core_title_zh]))
            _summary = " ".join(filter(None, [cluster.summary, cluster.summary_zh]))
            cluster.is_ai_relevant = is_ai_related(_title, _summary)


preprocess_pipeline = PreprocessPipeline()

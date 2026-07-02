"""Adapter 总调度：读 SourceRegistry → 匹配 adapter → 写 RawInfo。

不负责选题衍生 / 评分（那是 Agent A/B 的事）。
"""

import asyncio
import logging
from datetime import datetime
from app.core.timezone import utcnow
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.raw_info import RawInfo, RAW_STATE_PENDING
from app.models.source_registry import SourceRegistry, SourceAccount
from app.services.scraping.base import FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)


class ScrapingOrchestrator:
    """注册 adapter，按 SourceRegistry 派发，落库 RawInfo。"""

    def __init__(self):
        self._adapters: Dict[str, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter) -> None:
        if not adapter.source_type:
            raise ValueError(f"Adapter {adapter} missing source_type")
        self._adapters[adapter.source_type] = adapter

    def get_adapter(self, source_type: str) -> Optional[SourceAdapter]:
        return self._adapters.get(source_type)

    async def fetch_all(
        self,
        db: AsyncSession,
        *,
        source_types: Optional[Sequence[str]] = None,
        platforms: Optional[Sequence[str]] = None,
        only_enabled: bool = True,
    ) -> Dict[str, Any]:
        """主入口：选出需要抓的 SourceRegistry → 并发抓 → 写库。"""
        stmt = select(SourceRegistry)
        if only_enabled:
            stmt = stmt.where(SourceRegistry.enabled.is_(True))
        if source_types:
            stmt = stmt.where(SourceRegistry.source_type.in_(list(source_types)))
        if platforms:
            stmt = stmt.where(SourceRegistry.platform.in_(list(platforms)))
        sources: List[SourceRegistry] = (await db.execute(stmt)).scalars().all()

        # 预取每个 source 的 accounts（避免 N+1）
        accounts_by_src: Dict[int, List[SourceAccount]] = {}
        if sources:
            acc_stmt = select(SourceAccount).where(
                SourceAccount.source_registry_id.in_([s.id for s in sources]),
                SourceAccount.enabled.is_(True),
            )
            for acc in (await db.execute(acc_stmt)).scalars().all():
                accounts_by_src.setdefault(acc.source_registry_id, []).append(acc)

        # 限流并发抓取（最多 5 个同时跑，避免 API 限流）
        sem = asyncio.Semaphore(5)
        task_sources = []
        tasks = []
        for src in sources:
            adapter = self.get_adapter(src.source_type)
            if not adapter:
                logger.warning(f"无 adapter 处理 source_type={src.source_type} (source={src.name})")
                continue
            task_sources.append(src)

            async def _limited_fetch(a=adapter, s=src, accs=accounts_by_src.get(src.id, [])):
                async with sem:
                    return await self._fetch_one(a, s, accs)

            tasks.append(_limited_fetch())

        per_source = await asyncio.gather(*tasks, return_exceptions=True)

        stats: Dict[str, Any] = {
            "sources_total": len(sources),
            "sources_skipped_no_adapter": len(sources) - len(tasks),
            "sources_ok": 0,
            "sources_failed": 0,
            "items_fetched": 0,
            "items_new": 0,
            "items_duplicate": 0,
            "per_source": {},
        }
        commercial_detection_ids: List[int] = []

        for src, outcome in zip(task_sources, per_source):
            entry: Dict[str, Any] = {"platform": src.platform, "source_type": src.source_type}
            if isinstance(outcome, Exception):
                logger.error(f"[{src.platform}] 抓取失败: {outcome}")
                entry.update(status="failed", error=str(outcome))
                stats["sources_failed"] += 1
            else:
                items: List[FetchedItem] = outcome
                new_count, dup_count, new_raw_info_ids = await self._persist(db, src, items)
                if src.source_type in {"exa_wechat", "sogou_wechat", "gzh_explosive"}:
                    commercial_detection_ids.extend(new_raw_info_ids)
                entry.update(
                    status="ok",
                    fetched=len(items),
                    new=new_count,
                    duplicate=dup_count,
                )
                stats["sources_ok"] += 1
                stats["items_fetched"] += len(items)
                stats["items_new"] += new_count
                stats["items_duplicate"] += dup_count
                src.last_fetched_at = utcnow().isoformat()
            stats["per_source"][src.platform] = entry

        await db.commit()
        self._dispatch_commercial_detection(commercial_detection_ids)
        logger.info(
            f"orchestrator 完成: new={stats['items_new']} dup={stats['items_duplicate']} "
            f"ok={stats['sources_ok']} failed={stats['sources_failed']}"
        )
        return stats

    async def _fetch_one(
        self,
        adapter: SourceAdapter,
        source: SourceRegistry,
        accounts: List[SourceAccount],
    ) -> List[FetchedItem]:
        return await adapter.fetch(source, accounts=accounts or None)

    async def _persist(
        self,
        db: AsyncSession,
        source: SourceRegistry,
        items: Iterable[FetchedItem],
    ) -> tuple[int, int, List[int]]:
        new_count = 0
        dup_count = 0
        new_raw_info_ids: List[int] = []
        seen_hashes: set[str] = set()
        seen_urls: set[str] = set()
        for item in items:
            url = (item.url or "").strip()
            if not url:
                continue
            url_trunc = url[:1000]

            h = item.dedup_hash()
            # 同批次去重：flush 在循环外，DB 查询看不到本批刚 add 的记录，
            # 必须用内存 set 挡住同一批里的重复（标题指纹 + URL 双重挡）
            if h in seen_hashes or url_trunc in seen_urls:
                dup_count += 1
                continue

            # 跨批次去重：标题指纹 OR 精确 URL 命中即视为重复。
            # URL 唯一约束（ix_raw_infos_url）独立于标题 hash——同一 URL 换了标题
            # 也必须挡住，否则 flush 时触发 IntegrityError 导致整批回滚。
            existing = (await db.execute(
                select(RawInfo.id).where(
                    or_(RawInfo.dedup_hash == h, RawInfo.url == url_trunc)
                ).limit(1)
            )).first()
            if existing:
                dup_count += 1
                continue

            seen_hashes.add(h)
            seen_urls.add(url_trunc)
            raw = RawInfo(
                source_registry_id=source.id,
                source_account_id=item.source_account_id,
                title=(item.title or url)[:500],
                url=url[:1000],
                author=(item.author or "")[:200] or None,
                summary=item.summary,
                content=item.content,
                published_at=item.published_at,
                scraped_at=utcnow(),
                engagement=item.engagement or {},
                extras=item.extras or {},
                state=RAW_STATE_PENDING,
                dedup_hash=item.dedup_hash(),
            )
            db.add(raw)
            await db.flush()
            new_raw_info_ids.append(raw.id)
            new_count += 1
        return new_count, dup_count, new_raw_info_ids

    def _dispatch_commercial_detection(self, raw_info_ids: List[int]) -> None:
        """Fan out commercial detection without making scraping depend on Celery."""
        if not raw_info_ids:
            return
        try:
            from app.tasks.commercial_tasks import detect_commercial_task

            for raw_info_id in raw_info_ids:
                detect_commercial_task.delay(raw_info_id)
        except Exception as exc:
            logger.warning("商单检测任务派发失败，抓取结果已保留: %s", exc)


# 全局单例，adapter 在模块导入时自注册
orchestrator = ScrapingOrchestrator()

"""Adapter 总调度：读 SourceRegistry → 匹配 adapter → 写 RawInfo。

不负责选题衍生 / 评分（那是 Agent A/B 的事）。
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import select
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

        # 并发抓取（每个 source 一个 task）
        tasks = []
        for src in sources:
            adapter = self.get_adapter(src.source_type)
            if not adapter:
                logger.warning(f"无 adapter 处理 source_type={src.source_type} (source={src.name})")
                continue
            tasks.append(self._fetch_one(adapter, src, accounts_by_src.get(src.id, [])))

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

        for src, outcome in zip([s for s in sources if self.get_adapter(s.source_type)], per_source):
            entry: Dict[str, Any] = {"platform": src.platform, "source_type": src.source_type}
            if isinstance(outcome, Exception):
                logger.error(f"[{src.platform}] 抓取失败: {outcome}")
                entry.update(status="failed", error=str(outcome))
                stats["sources_failed"] += 1
            else:
                items: List[FetchedItem] = outcome
                new_count, dup_count = await self._persist(db, src, items)
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
                src.last_fetched_at = datetime.utcnow().isoformat()
            stats["per_source"][src.platform] = entry

        await db.commit()
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
    ) -> tuple[int, int]:
        new_count = 0
        dup_count = 0
        for item in items:
            url = (item.url or "").strip()
            if not url:
                continue
            existing = (await db.execute(
                select(RawInfo).where(RawInfo.url == url)
            )).scalar_one_or_none()
            if existing:
                dup_count += 1
                continue

            db.add(RawInfo(
                source_registry_id=source.id,
                source_account_id=item.source_account_id,
                title=(item.title or url)[:500],
                url=url[:1000],
                author=(item.author or "")[:200] or None,
                summary=item.summary,
                content=item.content,
                published_at=item.published_at,
                scraped_at=datetime.utcnow(),
                engagement=item.engagement or {},
                extras=item.extras or {},
                state=RAW_STATE_PENDING,
                dedup_hash=item.dedup_hash(),
            ))
            new_count += 1
        await db.flush()
        return new_count, dup_count


# 全局单例，adapter 在模块导入时自注册
orchestrator = ScrapingOrchestrator()

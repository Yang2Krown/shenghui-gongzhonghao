"""Adapter 抽象基类 + 统一数据契约。

每个 Adapter 只关心"怎么从这类源拿数据"，不关心入库——入库由 orchestrator 统一处理。
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.source_registry import SourceRegistry, SourceAccount

logger = logging.getLogger(__name__)


@dataclass
class FetchedItem:
    """Adapter 输出的标准化条目（对应一条 RawInfo）。"""
    title: str
    url: str
    summary: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    engagement: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)
    source_account_id: Optional[int] = None        # 命中的 SourceAccount（adapter 可选填）

    def dedup_hash(self) -> str:
        """内容指纹（sha256 前 16 位）。

        优先用规范化标题：同一篇文章经常有多个 URL（跟踪参数 / 短链 / s?__biz 形式），
        但标题一致，用标题去重能挡住这类"换皮重复"。无标题时再退回规范化 URL。
        """
        title = (self.title or "").strip().lower()
        base = title or (self.url or "").strip().rstrip("/").lower()
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


@dataclass
class AdapterHealth:
    """Adapter 健康状态（认证、外部依赖可用性）。"""
    ok: bool
    reason: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class SourceAdapter(ABC):
    """所有 adapter 的基类。

    一个 Adapter 实例负责一类 source_type（rss / web / github / exa_wechat / ...）。
    """

    # 子类必须填：对应 SourceRegistry.source_type
    source_type: str = ""

    def can_handle(self, source: SourceRegistry) -> bool:
        return source.source_type == self.source_type

    @abstractmethod
    async def fetch(
        self,
        source: SourceRegistry,
        *,
        accounts: Optional[List[SourceAccount]] = None,
        since: Optional[datetime] = None,
    ) -> List[FetchedItem]:
        """从 source 拉一批信息。

        - accounts：账号级订阅（X / 公众号），不需要时传 None
        - since：增量游标（未实现的 adapter 可忽略）
        """

    async def health_check(self) -> AdapterHealth:
        """默认健康为 OK；需要 cookie/外部 CLI 的子类应覆盖。"""
        return AdapterHealth(ok=True)

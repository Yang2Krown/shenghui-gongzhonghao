"""公众号爆款 adapter：整合 gzh-explosive-content-detector skill。

Skill 路径：~/.workbuddy/skills/gzh-explosive-content-detector/scripts/fetch_gzh_trends.py
通过 subprocess 调用，把 JSON 输出转成 FetchedItem。

榜单类型：
- 低粉高阅读（lowPowderExplosiveArticle）→ engagement.low_fan = True ⭐
- 阅读靠前（tenWReadingRank）
- 原创靠前（originalRank）
- 数据增长（oneWReadingRank）

SourceRegistry.fetch_config:
- keywords: List[str]  关键词列表（每个最多 5 个，逗号分隔后传给 skill）
- start_date: str (可选 YYYY-MM-DD)
- batch_size: int   一次 skill 调用塞几个关键词（默认 3）
"""

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_GZH_EXPLOSIVE
from app.services.scraping.base import FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)


# 优先用 repo 内 vendored 脚本；fallback 到本机 ~/.workbuddy（开发期方便）
_REPO_SKILL = Path(__file__).resolve().parents[4] / "external" / "skills" / "gzh_explosive" / "fetch_gzh_trends.py"
_LOCAL_SKILL = Path(os.path.expanduser(
    "~/.workbuddy/skills/gzh-explosive-content-detector/scripts/fetch_gzh_trends.py"
))
SKILL_SCRIPT = _REPO_SKILL if _REPO_SKILL.exists() else _LOCAL_SKILL


class GzhExplosiveAdapter(SourceAdapter):
    source_type = SOURCE_TYPE_GZH_EXPLOSIVE
    TIMEOUT = 90  # 单次 skill 调用最长 90s

    async def fetch(
        self,
        source: SourceRegistry,
        *,
        accounts: Optional[List[SourceAccount]] = None,
        since: Optional[datetime] = None,
    ) -> List[FetchedItem]:
        if not SKILL_SCRIPT.exists():
            logger.error(f"公众号爆款 skill 脚本不存在: {SKILL_SCRIPT}")
            return []

        cfg = source.fetch_config or {}
        keywords: List[str] = cfg.get("keywords") or [
            # 默认 AI 选题关键词集
            "AI Agent,大模型",
            "Claude,Codex,Cursor",
            "AI 视频,Sora,可灵",
            "AI 出图,Midjourney",
        ]
        start_date: Optional[str] = cfg.get("start_date")

        all_items: List[FetchedItem] = []
        seen_urls: set[str] = set()

        for kw_batch in keywords:
            items = await self._fetch_one(kw_batch, start_date)
            for it in items:
                if it.url not in seen_urls:
                    seen_urls.add(it.url)
                    all_items.append(it)

        logger.info(f"[{source.platform}] gzh_explosive 抓回 {len(all_items)} 条（关键词组 {len(keywords)} 个）")
        return all_items

    async def _fetch_one(self, keyword: str, start_date: Optional[str]) -> List[FetchedItem]:
        """调一次 skill 脚本，返回 FetchedItem 列表。"""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.close()
        out_path = tmp.name

        cmd = [
            "python3", str(SKILL_SCRIPT),
            "--keyword", keyword,
            "--output-format", "json",
            "--output-file", out_path,
        ]
        if start_date:
            cmd += ["--start-date", start_date]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.TIMEOUT)
            except asyncio.TimeoutError:
                proc.kill()
                logger.warning(f"gzh skill 超时: keyword='{keyword}'")
                return []

            if proc.returncode != 0:
                logger.warning(f"gzh skill 退出码 {proc.returncode}, keyword='{keyword}': {stderr.decode('utf-8','ignore')[:200]}")
                return []

            try:
                with open(out_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning(f"gzh skill JSON 读取失败 keyword='{keyword}': {e}")
                return []
        finally:
            try:
                os.unlink(out_path)
            except OSError:
                pass

        items_raw = data.get("items", [])
        return [it for it in (self._to_item(x) for x in items_raw) if it]

    @staticmethod
    def _to_item(x: Dict[str, Any]) -> Optional[FetchedItem]:
        url = (x.get("noteLink") or "").strip()
        title = (x.get("title") or "").strip()
        if not url or not title:
            return None

        category = x.get("category") or ""
        engagement = {
            "like": x.get("likeCount") or 0,
            "comments": x.get("commentCount") or 0,
            "share": x.get("shareCount") or 0,
            "interactive": x.get("interactiveCount") or 0,
            "category": category,
            # 低粉爆款标记：直接给上游 compute_low_fan_hit 用
            "low_fan": category == "低粉高阅读",
        }

        published_at = None
        if x.get("publicTime"):
            try:
                published_at = datetime.strptime(x["publicTime"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

        return FetchedItem(
            title=title,
            url=url,
            summary=(x.get("summary") or "").strip()[:500] or None,
            author=(x.get("accountName") or x.get("userName") or None),
            published_at=published_at,
            engagement=engagement,
            extras={
                "fans": x.get("fans"),
                "account_id": x.get("accountId"),
                "photo_id": x.get("photoId"),
                "category": category,
            },
        )

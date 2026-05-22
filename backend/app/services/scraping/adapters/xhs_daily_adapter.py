"""小红书每日爆款 adapter（SkillHub API，0 cookie）。

数据来源：xhs-daily-breaking skill 同一个 API（onetotenvip.com）。
- 每日 19:00 更新昨日榜单
- 25 个分类的 TOP 50

为什么不走 subprocess：
- 脚本输出 Markdown 不是 JSON
- 直接 httpx 调 API 更快、更稳

SourceRegistry.fetch_config:
- categories: List[str]   分类名（默认 ["综合全部", "数码科技", "学习教育"]）
- top_n: int              每分类拉前 N 条（默认 50）
- rank_date: str          可选 yyyy-MM-dd；缺省按 skill 规则自动：< 19:00 用前天，>= 19:00 用昨天
- low_fan_threshold: int  fans < 此值视为"低粉爆款"（默认 10000）
"""

import asyncio
import importlib.util
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_XHS_DAILY
from app.services.scraping.base import FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)


# 把 vendored skill 脚本 import 进来，复用 fetch_explosive_articles（含无 SNI HTTPS）
_SKILL_PATH = Path(__file__).resolve().parents[4] / "external" / "skills" / "xhs_daily" / "xhs_daily_fetcher.py"


def _load_skill_module():
    """动态加载 vendored skill 脚本为 Python module。"""
    spec = importlib.util.spec_from_file_location("xhs_daily_skill", _SKILL_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["xhs_daily_skill"] = mod
    spec.loader.exec_module(mod)
    return mod


_skill_cache = None


def _get_skill():
    global _skill_cache
    if _skill_cache is None:
        _skill_cache = _load_skill_module()
    return _skill_cache

DEFAULT_CATEGORIES = ["综合全部", "数码科技", "学习教育"]

# 全量 25 个分类（参考 xhs_daily_fetcher.py CATEGORY_KEYWORDS keys）
ALL_CATEGORIES = [
    "综合全部", "数码科技", "学习教育", "职业发展", "化妆美容",
    "居家装修", "拍摄记录", "美味佳肴", "时尚穿搭", "出行代步",
    "休闲爱好", "影视娱乐", "医疗保健", "综合杂项", "星座情感",
    "婚庆婚礼", "亲子育儿", "个人护理", "宠物天地", "潮流鞋包",
    "日常生活", "科学探索", "新闻资讯", "体育锻炼",
]


def _parse_count(value) -> int:
    """支持 "2w+" 这种格式。"""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if not v:
            return 0
        if "w" in v:
            try:
                return int(float(v.replace("w+", "").replace("w", "")) * 10000)
            except Exception:
                return 0
        try:
            return int(v)
        except Exception:
            return 0
    return 0


def _resolve_default_date() -> str:
    """按 skill 规则确定默认查询日期。"""
    now = datetime.now()
    cutoff = now.replace(hour=19, minute=0, second=0, microsecond=0)
    target = (now - timedelta(days=1)) if now >= cutoff else (now - timedelta(days=2))
    return target.strftime("%Y-%m-%d")


class XhsDailyAdapter(SourceAdapter):
    source_type = SOURCE_TYPE_XHS_DAILY

    async def fetch(
        self,
        source: SourceRegistry,
        *,
        accounts: Optional[List[SourceAccount]] = None,
        since: Optional[datetime] = None,
    ) -> List[FetchedItem]:
        cfg = source.fetch_config or {}
        categories: List[str] = cfg.get("categories") or DEFAULT_CATEGORIES
        top_n = int(cfg.get("top_n", 50))
        rank_date = cfg.get("rank_date") or _resolve_default_date()
        low_fan_threshold = int(cfg.get("low_fan_threshold", 10000))

        try:
            skill = _get_skill()
        except Exception as e:
            logger.error(f"无法加载 xhs_daily skill 脚本: {e}")
            return []

        all_items: List[FetchedItem] = []
        seen_urls: set[str] = set()

        for category in categories:
            items = await self._fetch_category(skill, rank_date, category, top_n, low_fan_threshold)
            for it in items:
                if it.url not in seen_urls:
                    seen_urls.add(it.url)
                    all_items.append(it)

        logger.info(
            f"[{source.platform}] xhs_daily 抓回 {len(all_items)} 条（{len(categories)} 分类 / 日期 {rank_date}）"
        )
        return all_items

    async def _fetch_category(
        self,
        skill,
        rank_date: str,
        category: str,
        top_n: int,
        low_fan_threshold: int,
    ) -> List[FetchedItem]:
        # skill 的 fetch_explosive_articles 是同步阻塞（socket），用 thread 包一下
        def _sync_fetch():
            try:
                return skill.fetch_explosive_articles(rank_date, category)
            except Exception as e:
                logger.warning(f"xhs_daily 请求失败 [{category}/{rank_date}]: {e}")
                return None

        data = await asyncio.to_thread(_sync_fetch)
        if not data:
            return []

        articles = skill.process_ranking_data(data, top_n)
        if not articles:
            return []

        items: List[FetchedItem] = []
        for art in articles:
            it = self._to_item(art, category, rank_date, low_fan_threshold)
            if it:
                items.append(it)
        return items

    @staticmethod
    def _to_item(art: Dict[str, Any], category: str, rank_date: str, low_fan_threshold: int) -> Optional[FetchedItem]:
        title = (art.get("title") or "").strip()
        url = (art.get("photoJumpUrl") or "").strip()
        if not title or not url:
            return None

        # 互动数据：anaAdd 套层 + 顶层兜底
        ana_add = art.get("anaAdd") or {}
        like = _parse_count(ana_add.get("useLikeCount") or art.get("useLikeCount") or 0)
        comment = _parse_count(ana_add.get("useCommentCount") or art.get("useCommentCount") or 0)
        collect = _parse_count(ana_add.get("collectedCount") or art.get("collectedCount") or 0)
        share = _parse_count(ana_add.get("useShareCount") or art.get("useShareCount") or 0)
        interactive = _parse_count(ana_add.get("interactiveCount") or art.get("interactiveCount") or 0)
        # 新增量（爆发幅度）
        add_interactive = _parse_count(ana_add.get("addInteractiveount") or 0)
        add_like = _parse_count(ana_add.get("addLikeCount") or 0)

        fans = _parse_count(art.get("fans") or 0)
        # 低粉爆款：粉丝低 + 互动高
        low_fan = fans < low_fan_threshold and interactive > 1000

        published_at = None
        for fld in ("publicTime", "publishTime", "createTime"):
            if art.get(fld):
                try:
                    published_at = datetime.strptime(str(art[fld]), "%Y-%m-%d %H:%M:%S")
                    break
                except Exception:
                    continue

        return FetchedItem(
            title=title,
            url=url,
            summary=(art.get("desc") or "").strip()[:500] or None,
            author=art.get("userName") or None,
            published_at=published_at,
            engagement={
                "like": like,
                "comments": comment,
                "collect": collect,
                "share": share,
                "interactive": interactive,
                "add_interactive": add_interactive,
                "add_like": add_like,
                "low_fan": low_fan,
            },
            extras={
                "xhs_category": category,
                "xhs_rank_date": rank_date,
                "fans": fans,
                "user_jump_url": art.get("userJumpUrl"),
                "cover_url": art.get("coverUrl") or art.get("imageUrl"),
            },
        )

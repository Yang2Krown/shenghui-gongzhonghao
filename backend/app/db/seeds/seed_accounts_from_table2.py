"""Seed: 关注博主整理_AI信息源.xlsx → SourceAccount。

87 个账号：58 X/Twitter + 29 微信公众号。
- X 账号挂在 platform='x' 的 SourceRegistry 下（requires_auth=True, P1 阶段启用）
- 公众号账号挂在 platform='exa_wechat' 下（搜索流，0 cookie）
  抓取时把 display_name 当作 Exa 搜索关键词，配合 includeDomains=mp.weixin.qq.com 过滤。
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple

import openpyxl
from sqlalchemy import select

from app.db.seeds import TABLE2_PATH
from app.db.session import AsyncSessionLocal
from app.models.source_registry import (
    SourceRegistry,
    SourceAccount,
    SOURCE_TYPE_X,
    SOURCE_TYPE_EXA_WECHAT,
)

logger = logging.getLogger(__name__)


# 表 2 使用建议 sheet 给出的"每日必看 / 深度研究 / AI编程 / 中文内容参考" 名单，
# 用于打 priority 标签
PRIORITY_KEYWORDS = {
    "每日必看": {"Gorden Sun", "小互", "量子位", "36氪", "Chetaslua", "Nav Toor", "歸藏", "歸藏(guizang.ai)"},
    "深度研究": {"Anthropic", "Dario Amodei", "Sam Bowman", "Rachel Freedman", "Berkeley AI Research", "Stanford NLP Group"},
    "AI编程/Agent": {"Boris Cherny", "Claude Code Community", "Thariq", "OpenClaw", "Luyu Zhang", "Henry Heng", "PyTorch"},
    "中文内容参考": {"AYi", "开发者Hailey", "鱼总聊AI", "vigorxu", "宝玉", "优设AIGC", "路人甲TM"},
}


async def _ensure_registry(db, *, platform: str, name: str, source_type: str,
                            requires_auth: bool, description: str) -> SourceRegistry:
    existing = (await db.execute(
        select(SourceRegistry).where(SourceRegistry.platform == platform)
    )).scalar_one_or_none()
    if existing:
        return existing
    reg = SourceRegistry(
        name=name,
        platform=platform,
        source_type=source_type,
        url=None,
        tier=3 if platform == "x" else 6,
        direction_tags=[],
        weight=5,
        requires_auth=requires_auth,
        auth_status="missing" if requires_auth else "ok",
        fetch_strategy="cron",
        fetch_config={},
        enabled=not requires_auth,                # P0 阶段：X 暂时停用，公众号启用
        description=description,
    )
    db.add(reg)
    await db.flush()
    return reg


def _infer_priority(name: str) -> Optional[str]:
    for label, names in PRIORITY_KEYWORDS.items():
        if any(target in (name or "") for target in names):
            return label
    return None


async def _upsert_account(db, *, registry_id: int, handle: Optional[str], display_name: str,
                          verified: Optional[str], category: Optional[str],
                          description: Optional[str], suitable_for: Optional[str],
                          note: Optional[str]) -> str:
    # 优先按 (registry_id, handle) 唯一；handle 缺失时按 (registry_id, display_name)
    if handle:
        stmt = select(SourceAccount).where(
            SourceAccount.source_registry_id == registry_id,
            SourceAccount.handle == handle,
        )
    else:
        stmt = select(SourceAccount).where(
            SourceAccount.source_registry_id == registry_id,
            SourceAccount.handle.is_(None),
            SourceAccount.display_name == display_name,
        )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    fields = dict(
        display_name=display_name,
        verified=verified,
        category=category,
        description=description,
        suitable_for=suitable_for,
        priority=_infer_priority(display_name),
        note=note,
        enabled=True,
    )

    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
        return "updated"

    db.add(SourceAccount(source_registry_id=registry_id, handle=handle, **fields))
    return "created"


async def run(db) -> dict:
    if not Path(TABLE2_PATH).exists():
        raise FileNotFoundError(f"Seed file missing: {TABLE2_PATH}")

    wb = openpyxl.load_workbook(TABLE2_PATH, data_only=True)
    ws = wb["博主清单"]

    x_reg = await _ensure_registry(
        db,
        platform="x",
        name="X / Twitter 关注博主",
        source_type=SOURCE_TYPE_X,
        requires_auth=True,
        description="重点关注的 X/Twitter 博主清单（P1 阶段启用，需 Cookie）",
    )
    wechat_reg = await _ensure_registry(
        db,
        platform="exa_wechat",
        name="微信公众号关键词搜索流",
        source_type=SOURCE_TYPE_EXA_WECHAT,
        requires_auth=False,
        description="基于 Exa 的公众号文章搜索（关键词 = 公众号名 / 直接关键词）",
    )

    stats = {"created": 0, "updated": 0, "skipped": 0}

    # 列序：序号 / 平台 / 名称 / Handle / 认证 / 领域分类 / 简介 / 适合参考 / 备注
    for row in ws.iter_rows(min_row=2, values_only=True):
        cols = (row + (None,) * 9)[:9]
        _idx, platform_label, name, handle, verified, category, desc, suitable, note = cols
        if not name:
            stats["skipped"] += 1
            continue

        if platform_label and "X" in str(platform_label):
            registry_id = x_reg.id
        elif platform_label and "公众号" in str(platform_label):
            registry_id = wechat_reg.id
        else:
            stats["skipped"] += 1
            continue

        outcome = await _upsert_account(
            db,
            registry_id=registry_id,
            handle=str(handle).strip() if handle else None,
            display_name=str(name).strip(),
            verified=str(verified).strip() if verified else None,
            category=str(category).strip() if category else None,
            description=str(desc).strip() if desc else None,
            suitable_for=str(suitable).strip() if suitable else None,
            note=str(note).strip() if note else None,
        )
        stats[outcome] += 1

    await db.commit()
    logger.info(f"seed_accounts_from_table2: {stats}")
    return stats


async def _main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    async with AsyncSessionLocal() as db:
        result = await run(db)
    print(f"Done: {result}")


if __name__ == "__main__":
    asyncio.run(_main())

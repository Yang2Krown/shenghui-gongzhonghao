"""Seed: 关注博主整理_AI信息源.xlsx → SourceAccount。

87 个账号：58 X/Twitter + 29 微信公众号。
- X 账号挂在 platform='x' 的 SourceRegistry 下，走 twitterapi.io（国内直连，无需 Cookie）。
  另建 platform='x_search' 同 source_type='x'，跑中英文 AI 主题词关键词搜索。
- 公众号账号挂在 platform='sogou_wechat_cases' 下（保留历史 platform 名称，避免迁移账号）
  但 source_type 已切到 dajiala_wechat，走极致了 post_condition/post_history。
  （历史上曾走 Exa/搜狗；本 seed 幂等地把存量公众号账号迁过来，无需手动维护。）
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple

import openpyxl
from sqlalchemy import select, update

from app.db.seeds import TABLE2_PATH
from app.db.session import AsyncSessionLocal
from app.models.source_registry import (
    SourceRegistry,
    SourceAccount,
    SOURCE_TYPE_X,
    SOURCE_TYPE_DAJIALA_WECHAT,
)

logger = logging.getLogger(__name__)


# 关键词搜索（platform=x_search）用的 AI 主题词：中文复用现有 sogou 主题词，
# 再补一批英文——X 上 AI 圈以英文为主，中文词主要命中中文圈推文。
X_KEYWORDS_CN = [
    "大模型", "AI Agent", "Coding Agent", "Claude", "ChatGPT", "DeepSeek",
    "Cursor", "AI 编程", "vibe coding", "Sora", "AI 视频", "Midjourney",
    "提示词", "MCP", "智能体", "多模态", "开源模型", "具身智能",
]
X_KEYWORDS_EN = [
    "generative AI", "LLM", "Claude AI", "GPT-5", "open source LLM", "RAG",
    "AI coding", "agentic AI", "fine-tuning", "multimodal", "prompt engineering",
    "MCP protocol", "AI startup", "LLM inference", "AI research",
]
X_KEYWORDS = X_KEYWORDS_CN + X_KEYWORDS_EN


# 表 2 使用建议 sheet 给出的"每日必看 / 深度研究 / AI编程 / 中文内容参考" 名单，
# 用于打 priority 标签
PRIORITY_KEYWORDS = {
    "每日必看": {"Gorden Sun", "小互", "量子位", "36氪", "Chetaslua", "Nav Toor", "歸藏", "歸藏(guizang.ai)"},
    "深度研究": {"Anthropic", "Dario Amodei", "Sam Bowman", "Rachel Freedman", "Berkeley AI Research", "Stanford NLP Group"},
    "AI编程/Agent": {"Boris Cherny", "Claude Code Community", "Thariq", "OpenClaw", "Luyu Zhang", "Henry Heng", "PyTorch"},
    "中文内容参考": {"AYi", "开发者Hailey", "鱼总聊AI", "vigorxu", "宝玉", "优设AIGC", "路人甲TM"},
}

WECHAT_COMMERCIAL_ACCOUNT_NAMES = [
    "苍何",
    "袋鼠帝AI客栈",
    "莫理",
    "卡尔的AI沃兹",
    "公子龙",
    "阿枫科技",
    "数字生命卡兹克",
    "路人甲TM",
    "仙人甲",
    "网罗灯下黑",
    "猫狸智元",
    "软件科技汇",
]

WECHAT_COMMERCIAL_ACCOUNT_ALIASES = {
    "路人甲 TM": "路人甲TM",
    "卡尔的AI沃茨": "卡尔的AI沃兹",
}


async def _ensure_registry(db, *, platform: str, name: str, source_type: str,
                            requires_auth: bool, description: str,
                            fetch_config: Optional[dict] = None) -> SourceRegistry:
    existing = (await db.execute(
        select(SourceRegistry).where(SourceRegistry.platform == platform)
    )).scalar_one_or_none()
    if existing:
        # 幂等：确保关键配置就位（如搜狗案例源的 max_keywords，避免 29 个号被默认 20 截断）
        if fetch_config is not None:
            existing.fetch_config = fetch_config
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
        fetch_config=fetch_config or {},
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
    # 历史数据可能已有重复账号；seed 必须幂等且不能因重复记录中断整批导入。
    existing = (await db.execute(stmt.order_by(SourceAccount.id))).scalars().first()

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


async def _sync_wechat_commercial_accounts(db, registry_id: int) -> dict:
    """Only keep the curated WeChat creators used for commercial monitoring."""
    wanted = set(WECHAT_COMMERCIAL_ACCOUNT_NAMES)
    existing_rows = (await db.execute(
        select(SourceAccount).where(SourceAccount.source_registry_id == registry_id)
    )).scalars().all()
    by_name = {}
    disabled = 0
    renamed = 0
    deduped = 0

    for old_name, new_name in WECHAT_COMMERCIAL_ACCOUNT_ALIASES.items():
        account = next((a for a in existing_rows if a.display_name == old_name), None)
        if account:
            account.display_name = new_name
            account.enabled = True
            renamed += 1

    for account in sorted(existing_rows, key=lambda a: a.id or 0):
        if account.display_name in wanted and account.display_name not in by_name:
            by_name[account.display_name] = account
            continue
        if account.enabled:
            account.enabled = False
            if account.display_name in wanted:
                deduped += 1
            else:
                disabled += 1

    created = 0
    reenabled = 0
    for name in WECHAT_COMMERCIAL_ACCOUNT_NAMES:
        account = by_name.get(name)
        if account:
            if not account.enabled:
                account.enabled = True
                reenabled += 1
            account.handle = account.handle or None
            account.category = account.category or "公众号商单监控"
            account.priority = account.priority or "商单监控"
            continue
        db.add(SourceAccount(
            source_registry_id=registry_id,
            handle=None,
            display_name=name,
            verified=None,
            category="公众号商单监控",
            description=None,
            suitable_for=None,
            priority="商单监控",
            note="固定商单监控博主",
            enabled=True,
        ))
        created += 1

    return {
        "created": created,
        "reenabled": reenabled,
        "disabled": disabled,
        "renamed": renamed,
        "deduped": deduped,
    }


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
        requires_auth=False,
        description="重点关注的 X/Twitter 博主清单，走 twitterapi.io（国内直连，无需 Cookie/代理）。每天 1 次，串行定速跑完。",
        # 账号模式：不设 keywords。每个号取最近 20 条。免费档 QPS=1 req/5s → 串行(concurrency=1)，
        # 58 个号约 5 分钟跑完。升级套餐后可调高 concurrency / 调低 min_interval_sec。
        fetch_config={"limit": 20, "concurrency": 1, "include_replies": False},
    )
    # 幂等：旧 seed 曾把 x 源设成 enabled=False/requires_auth=True（等 Cookie 方案）。
    # 现在改走 twitterapi.io，强制打开 + 改成免鉴权（key 在 .env，不走 requires_auth/cookie 这套）。
    x_reg.requires_auth = False
    x_reg.auth_status = "ok"
    x_reg.enabled = True

    x_search_reg = await _ensure_registry(
        db,
        platform="x_search",
        name="X / Twitter 关键词搜索",
        source_type=SOURCE_TYPE_X,
        requires_auth=False,
        description="X 关键词搜索（twitterapi.io advanced_search）。中英文 AI 主题词，按时间片轮转分批，防一次发太多。",
        # 关键词模式：配了 keywords → adapter 走 advanced_search。
        # rotate_batch=10 + 每 4h 轮转：~39 个词分多批，一天覆盖一轮，单次请求量小。
        fetch_config={
            "keywords": X_KEYWORDS,
            "query_type": "Latest",
            "limit": 20,
            "concurrency": 1,          # 免费档 QPS=1 req/5s，串行定速
            "rotate_batch": 10,
            "rotate_period_sec": 14400,
        },
    )
    x_search_reg.enabled = True
    wechat_reg = await _ensure_registry(
        db,
        platform="sogou_wechat_cases",
        name="公众号案例源（极致了）",
        source_type=SOURCE_TYPE_DAJIALA_WECHAT,
        requires_auth=False,
        description="重点案例公众号，走极致了接口。日常 post_condition 查当天发文，历史补库由专门任务调用 post_history。",
        fetch_config={"concurrency": 2, "history_concurrency": 2},
    )
    # 幂等：历史上该 platform 是搜狗源。保留 platform/source_account 外键，只切换抓取实现。
    wechat_reg.name = "公众号案例源（极致了）"
    wechat_reg.source_type = SOURCE_TYPE_DAJIALA_WECHAT
    wechat_reg.requires_auth = False
    wechat_reg.auth_status = "ok"
    wechat_reg.enabled = True
    wechat_reg.description = "重点案例公众号，走极致了接口。日常 post_condition 查当天发文，历史补库由专门任务调用 post_history。"
    wechat_reg.fetch_config = {"concurrency": 2, "history_concurrency": 2}

    # 存量迁移（幂等）：把旧 exa_wechat 源下的公众号账号整体改挂到搜狗案例源，
    # 保留 raw_infos.source_account_id 的外键引用、避免重复账号；并禁用欠费的 exa。
    exa_old = (await db.execute(
        select(SourceRegistry).where(SourceRegistry.platform == "exa_wechat")
    )).scalar_one_or_none()
    if exa_old is not None and exa_old.id != wechat_reg.id:
        await db.execute(
            update(SourceAccount)
            .where(SourceAccount.source_registry_id == exa_old.id)
            .values(source_registry_id=wechat_reg.id)
        )
        exa_old.enabled = False
        await db.flush()

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
            canonical_name = WECHAT_COMMERCIAL_ACCOUNT_ALIASES.get(str(name).strip(), str(name).strip())
            if canonical_name not in WECHAT_COMMERCIAL_ACCOUNT_NAMES:
                stats["skipped"] += 1
                continue
            name = canonical_name
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

    stats["wechat_curated"] = await _sync_wechat_commercial_accounts(db, wechat_reg.id)

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

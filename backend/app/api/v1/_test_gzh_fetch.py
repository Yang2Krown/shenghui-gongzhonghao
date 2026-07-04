"""⚠️ 实验性测试路由 —— 仅用于临时排查"公众号抓取到了什么"，feature 验证完毕后整文件删除。

能力：读现有 RawInfo（exa_wechat / sogou_wechat / gzh_explosive），
      按公众号聚合，让你单独看每个号抓了多少、历史怎样、数据是否有问题。

一文件一组 endpoint。只读 RawInfo / SourceAccount / SourceRegistry，
不新增模型、不新增表（零 migration）、不新增调度、不改现有功能。
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin_user
from app.db.session import get_db
from app.models.raw_info import RawInfo
from app.models.source_registry import SourceRegistry, SourceAccount

router = APIRouter(dependencies=[Depends(get_current_admin_user)])

# 当前被视为"公众号"的 source_type 集合 — 要加新类型直接展开这行
GZH_SOURCE_TYPES = ("exa_wechat", "sogou_wechat", "gzh_explosive")


class AccountArticlesResponse(BaseModel):
    """单个公众号的文章条目（用于前端展示）."""

    id: int
    title: str
    url: str
    author: Optional[str]
    summary: Optional[str]
    published_at: Optional[str]
    scraped_at: Optional[str]
    commercial_level: str


class AccountInfo(BaseModel):
    """单个公众号的聚合统计."""

    source_account_id: Optional[int]
    source_registry_id: int               # ★ 新增：前端查文章的关键 ID（null-account 也用这个）
    account_name: str                   # 公众号名（SourceAccount.display_name）
    handle: Optional[str]               # 公众号 ID（SourceAccount.handle）
    platform: str                       # 走的哪个平台：exa / sogou / gzh_explosive
    articles_count: int
    first_scraped_at: Optional[str]
    last_scraped_at: Optional[str]


class TestGzhFetchResponse(BaseModel):
    """GET /summary 响应体."""

    total_accounts: int
    total_articles: int
    accounts: List[AccountInfo]


# ── 端点 ─────────────────────────────────────────────────


@router.get("/__ping__", response_model=dict)
async def _ping() -> Any:
    """极简探活端点：确认后端路由加载成功 + 账号路由 prefix 生效."""
    return {"code": 200, "ok": True, "data": {
        "prefix": "/api/v1/_test_gzh_fetch",
        "routes": ["/summary", "/articles", "/account/{id}", "/ungrouped/{registry_id}", "/__ping__"],
    }}


@router.get("/summary", response_model=dict)
async def gzh_summary(
    db: AsyncSession = Depends(get_db),
) -> Any:
    """公众号抓取总览：每个号抓了多少篇、最早最新什么时候。

    说明：大多数公众号没绑定 SourceAccount（搜索结果没匹配回来），
    后端把没账号的文章自动归到「platform + '-未分组'」虚拟行。
    这行前端仍可点击，点进去按 source_registry_id + source_account_id IS NULL 筛，
    等价于「该平台上所有没匹配到订阅号的文章」。
    """

    # 聚合：每个 (source_account_id, source_registry_id) 的计数 + 时间跨度
    rows = (await db.execute(
        select(
            RawInfo.source_account_id,
            RawInfo.source_registry_id,
            func.count(RawInfo.id).label("articles_count"),
            func.min(RawInfo.scraped_at).label("first_scraped"),
            func.max(RawInfo.scraped_at).label("last_scraped"),
        )
        .where(
            RawInfo.source_registry_id.in_(
                select(SourceRegistry.id).where(
                    SourceRegistry.source_type.in_(GZH_SOURCE_TYPES)
                )
            )
        )
        .group_by(RawInfo.source_account_id, RawInfo.source_registry_id)
        .order_by(func.count(RawInfo.id).desc())
    )).all()  # type: ignore[var-annotated]

    # 拉取涉及的 SourceAccount 与 SourceRegistry.platform（各一次，均在内存建 dict）
    account_ids: List[int] = [r.source_account_id for r in rows if r.source_account_id]
    registry_ids: List[int] = list({r.source_registry_id for r in rows})

    acc_name: Dict[int, SourceAccount] = {}
    if account_ids:
        acc_rows = (await db.execute(
            select(SourceAccount).where(SourceAccount.id.in_(account_ids))
        )).scalars().all()
        acc_name = {a.id: a for a in acc_rows}

    reg_platform: Dict[int, str] = {}
    if registry_ids:
        reg_rows = (await db.execute(
            select(SourceRegistry.id, SourceRegistry.platform).where(SourceRegistry.id.in_(registry_ids))
        )).all()
        reg_platform = {r_id: plat for r_id, plat in reg_rows}

    accounts_info: List[AccountInfo] = []
    total_articles = 0
    for r in rows:
        acc = acc_name.get(r.source_account_id) if r.source_account_id else None
        plat = reg_platform.get(r.source_registry_id, "?")
        articles = r.articles_count or 0
        total_articles += articles
        # source_account_id 为 null → 没匹配到订阅号的，靠 platform 标记"未分组"
        display_name = acc.display_name if acc else f"{plat}-未分组"
        accounts_info.append(AccountInfo(
            source_account_id=r.source_account_id,    # 原样返回 null → 前端按 null 处理
            source_registry_id=r.source_registry_id,  # 必有
            account_name=display_name,
            handle=acc.handle if acc else None,
            platform=plat,
            articles_count=articles,
            first_scraped_at=r.first_scraped.isoformat() if r.first_scraped else None,
            last_scraped_at=r.last_scraped.isoformat() if r.last_scraped else None,
        ))

    resp = TestGzhFetchResponse(
        total_accounts=len(accounts_info),
        total_articles=total_articles,
        accounts=accounts_info,
    )
    return {"code": 200, "ok": True, "data": resp.dict()}


@router.get("/articles", response_model=dict)
async def gzh_articles(
    source_account_id: Optional[int] = Query(None, description="SourceAccount.id；不填=全平台聚合"),
    platform: Optional[str] = Query(None, description="按平台筛选：exa_wechat / sogou_wechat / gzh_explosive"),
    keyword: Optional[str] = Query(None, description="标题模糊匹配"),
    limit: int = Query(50, ge=1, le=500, description="返回条数上限"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """看某个公众号（或全平台）抓到的具体文章列表，按 scraped_at 倒序."""

    # 基础条件：公众号 source_type
    base_src_ids = select(SourceRegistry.id).where(
        SourceRegistry.source_type.in_(GZH_SOURCE_TYPES)
    )
    conditions = [RawInfo.source_registry_id.in_(base_src_ids)]
    if source_account_id is not None:
        conditions.append(RawInfo.source_account_id == source_account_id)
    if platform:
        # 先拿 platform 对应的 source_registry_id
        reg = (await db.execute(
            select(SourceRegistry).where(SourceRegistry.platform == platform)
        )).scalars().first()
        if not reg:
            raise HTTPException(status_code=404, detail=f"无 platform={platform} 的 source")
        conditions.append(RawInfo.source_registry_id == reg.id)
    if keyword:
        conditions.append(RawInfo.title.ilike(f"%{keyword}%"))

    # 总行数
    total = (await db.execute(
        select(func.count(RawInfo.id)).where(*conditions)
    )).scalar_one()

    # 分页数据
    rows = (await db.execute(
        select(RawInfo)
        .where(*conditions)
        .order_by(RawInfo.scraped_at.desc().nulls_last())
        .limit(limit)
        .offset(offset)
    )).scalars().all()

    items = [
        AccountArticlesResponse(
            id=r.id,
            title=r.title,
            url=r.url,
            author=r.author,
            summary=(r.summary or "")[:300] if r.summary else None,
            published_at=r.published_at.isoformat() if r.published_at else None,
            scraped_at=r.scraped_at.isoformat() if r.scraped_at else None,
            commercial_level=r.commercial_level or "none",
        ).dict()
        for r in rows
    ]

    return {"code": 200, "ok": True, "data": {
        "items": items,
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }}


@router.get("/account/{account_id:int}", response_model=dict)
async def gzh_single_account(
    account_id: int = Path(..., ge=1, description="SourceAccount.id；>0"),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """单个公众号详情：账号元信息 + 最近 N 篇文章."""

    acc = await db.get(SourceAccount, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="source_account 不存在")
    reg = await db.get(SourceRegistry, acc.source_registry_id)

    total = (await db.execute(
        select(func.count(RawInfo.id)).where(RawInfo.source_account_id == account_id)
    )).scalar_one()

    rows = (await db.execute(
        select(RawInfo)
        .where(RawInfo.source_account_id == account_id)
        .order_by(RawInfo.scraped_at.desc().nulls_last())
        .limit(limit)
    )).scalars().all()

    return {"code": 200, "ok": True, "data": {
        "account": {
            "id": acc.id,
            "display_name": acc.display_name,
            "handle": acc.handle,
            "category": acc.category,
            "priority": acc.priority,
            "platform": reg.platform if reg else None,
            "source_type": reg.source_type if reg else None,
        },
        "total": int(total),
        "items": [
            {
                "id": r.id,
                "title": r.title,
                "url": r.url,
                "author": r.author,
                "published_at": r.published_at.isoformat() if r.published_at else None,
                "scraped_at": r.scraped_at.isoformat() if r.scraped_at else None,
                "commercial_level": r.commercial_level or "none",
            }
            for r in rows
        ],
    }}


@router.get("/ungrouped/{registry_id:int}", response_model=dict)
async def gzh_ungrouped_registry(
    registry_id: int = Path(..., ge=1, description="SourceRegistry.id"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    keyword: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """查某个平台上「未匹配到订阅号」的文章（source_account_id IS NULL）。

    配合 /summary 中 platform='exa_wechat-未分组' 这行使用：前端点开这行时，
    传 registry_id，后端按 source_registry_id + source_account_id IS NULL 筛。
    """

    reg = await db.get(SourceRegistry, registry_id)
    if not reg or reg.source_type not in GZH_SOURCE_TYPES:
        raise HTTPException(status_code=404, detail="registry 不存在或不是公众号类型")

    conditions = [
        RawInfo.source_registry_id == registry_id,
        RawInfo.source_account_id.is_(None),
    ]
    if keyword:
        conditions.append(RawInfo.title.ilike(f"%{keyword}%"))

    total = (await db.execute(
        select(func.count(RawInfo.id)).where(*conditions)
    )).scalar_one()

    rows = (await db.execute(
        select(RawInfo).where(*conditions)
        .order_by(RawInfo.scraped_at.desc().nulls_last())
        .limit(limit).offset(offset)
    )).scalars().all()

    return {"code": 200, "ok": True, "data": {
        "account": {
            "id": None,
            "display_name": f"{reg.platform}-未分组",
            "handle": None,
            "category": "搜索结果未匹配到订阅号",
            "priority": None,
            "platform": reg.platform,
            "source_type": reg.source_type,
            "registry_id": registry_id,
        },
        "total": int(total),
        "items": [
            {
                "id": r.id,
                "title": r.title,
                "url": r.url,
                "author": r.author,
                "published_at": r.published_at.isoformat() if r.published_at else None,
                "scraped_at": r.scraped_at.isoformat() if r.scraped_at else None,
                "commercial_level": r.commercial_level or "none",
            }
            for r in rows
        ],
    }}

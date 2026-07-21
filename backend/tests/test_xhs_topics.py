from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.db.base import Base
from app.models.xhs import XhsKeyword, XhsKeywordRun
from app.services.xhs_topics import cosine_similarity, dbscan, evaluate_keyword_lifecycle, semantic_clusters

def test_dbscan_groups_by_content_vector_not_collection_keyword():
    # The first two can come from different search words; the third can share a
    # search word with the first and still stay outside its semantic cluster.
    vectors=[[1.0,0.0],[.99,.01],[0.0,1.0]]
    assert cosine_similarity(vectors[0],vectors[1])>.99
    assert dbscan(vectors,eps=.22,min_samples=2)==[[0,1]]


def test_average_link_does_not_chain_two_unrelated_topics_through_a_bridge():
    vectors=[[1.0,0.0],[.8,.6],[0.0,1.0]]
    # 两端彼此无关；中间内容不能把它们串成一个宽泛大话题。
    groups=semantic_clusters(vectors,threshold=.75)
    assert max((len(group) for group in groups),default=0)<=2


@pytest.mark.asyncio
async def test_existing_base_keyword_is_quarantined_after_three_successful_zero_yield_days():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for table in ("xhs_keywords","xhs_keyword_runs"): await conn.run_sync(Base.metadata.tables[table].create)
    async with AsyncSession(engine,expire_on_commit=False) as db:
        keyword=XhsKeyword(keyword="旧基础词",normalized_keyword="旧基础词",keyword_type="base",enabled=True,lifecycle_status="active",lifecycle_started_at=datetime(2026,7,18))
        db.add(keyword);await db.flush()
        for offset in range(3):
            day=date(2026,7,18)+timedelta(days=offset)
            db.add(XhsKeywordRun(keyword_id=keyword.id,run_date=day,wave="morning",status="completed",final_count=0));await db.commit()
            await evaluate_keyword_lifecycle(db,day)
        assert keyword.enabled is False
        assert keyword.lifecycle_status=="quarantined" and keyword.zero_yield_streak==3


@pytest.mark.asyncio
async def test_failed_day_does_not_increment_and_pinned_word_is_protected():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for table in ("xhs_keywords","xhs_keyword_runs"): await conn.run_sync(Base.metadata.tables[table].create)
    async with AsyncSession(engine,expire_on_commit=False) as db:
        keyword=XhsKeyword(keyword="置顶词",normalized_keyword="置顶词",enabled=True,lifecycle_status="active",pinned=True,zero_yield_streak=2)
        db.add(keyword);await db.flush();day=date(2026,7,18)
        db.add(XhsKeywordRun(keyword_id=keyword.id,run_date=day,wave="morning",status="risk_blocked",final_count=0));await db.commit()
        await evaluate_keyword_lifecycle(db,day);assert keyword.zero_yield_streak==2
        db.add(XhsKeywordRun(keyword_id=keyword.id,run_date=day+timedelta(days=1),wave="morning",status="completed",final_count=0));await db.commit()
        await evaluate_keyword_lifecycle(db,day+timedelta(days=1));assert keyword.enabled is True and keyword.zero_yield_streak==3

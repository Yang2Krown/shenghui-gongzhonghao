"""经验语义重合检测与合并的单元测试。"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1 import experience as experience_api
from app.models.content_version import ExperienceCard
from app.models.user import User
from app.services.experience_merge_service import (
    ExperienceMergeError,
    find_overlapping_cards,
    find_similar_cards,
    merge_experiences,
)


def _user(user_id: int, role: str = "admin") -> User:
    return User(
        id=user_id,
        username=f"merge-user-{user_id}",
        full_name=f"合并用户{user_id}",
        role=role,
        is_active=True,
        is_superuser=False,
    )


def _card(card_id: int, *, title: str, content: str, embedding=None, category: str = "开头") -> ExperienceCard:
    return ExperienceCard(
        id=card_id,
        title=title,
        content=content,
        category=category,
        source_type="manual",
        status="confirmed",
        embedding=embedding,
        embedding_status="ready" if embedding else "waiting",
        created_by=1,
    )


@pytest.fixture
async def merge_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: User.metadata.create_all(
                sync_conn,
                tables=[User.__table__, ExperienceCard.__table__],
            )
        )
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_find_overlapping_cards_groups_semantically_similar(merge_db):
    async with merge_db() as db:
        db.add(_user(1))
        # 两条几乎同向的向量（高余弦相似度），一条方向不同。
        near_a = [1.0, 0.0, 0.0]
        near_b = [0.99, 0.01, 0.0]
        far = [0.0, 1.0, 0.0]
        db.add_all([
            _card(1, title="开头先写冲突", content="开头先让读者看到具体冲突", embedding=near_a),
            _card(2, title="开头要呈现矛盾", content="文章开头要先呈现矛盾和冲突", embedding=near_b),
            _card(3, title="结尾要有行动号召", content="结尾引导读者采取行动", embedding=far),
        ])
        await db.commit()

        groups = await find_overlapping_cards(db, threshold=0.8)
        assert len(groups) == 1
        ids = sorted(card["id"] for card in groups[0]["cards"])
        assert ids == [1, 2]
        assert groups[0]["max_similarity"] >= 0.8


@pytest.mark.asyncio
async def test_find_similar_cards_excludes_self_and_low_score(merge_db):
    async with merge_db() as db:
        db.add(_user(1))
        db.add_all([
            _card(1, title="目标卡", content="目标卡内容", embedding=[1.0, 0.0]),
            _card(2, title="相似卡", content="相似内容", embedding=[0.95, 0.05]),
            _card(3, title="无关卡", content="无关内容", embedding=[0.0, 1.0]),
        ])
        await db.commit()

        similar = await find_similar_cards(db, 1, threshold=0.5)
        ids = [item["id"] for item in similar]
        assert 1 not in ids
        assert 2 in ids
        assert 3 not in ids


@pytest.mark.asyncio
async def test_merge_marks_other_sources_merged_and_keeps_survivor(merge_db):
    async with merge_db() as db:
        db.add(_user(1))
        db.add_all([
            _card(1, title="经验一", content="内容一", embedding=[1.0, 0.0]),
            _card(2, title="经验二", content="内容二", embedding=[0.9, 0.1]),
        ])
        await db.commit()

        # 避免真实入队 embedding 任务。
        async def fake_enqueue(card, session):
            return {"status": "queued"}

        experience_api.enqueue_embedding = fake_enqueue

        survivor = await merge_experiences(
            db,
            [1, 2],
            surviving_id=1,
            title="合并后的标题",
            content="合并后的完整内容",
            category="结构",
        )
        assert survivor.id == 1
        assert survivor.title == "合并后的标题"
        assert survivor.content == "合并后的完整内容"
        assert survivor.category == "结构"
        assert survivor.status == "confirmed"
        merged_from = survivor.source_meta["merged_from"]
        assert len(merged_from) == 1
        assert merged_from[0]["id"] == 2

        merged_card = await db.get(ExperienceCard, 2)
        assert merged_card.status == "merged"
        assert merged_card.source_meta["merged_into"] == 1


@pytest.mark.asyncio
async def test_merge_rejects_non_confirmed_or_missing(merge_db):
    async with merge_db() as db:
        db.add(_user(1))
        db.add_all([
            _card(1, title="正式经验", content="内容", embedding=[1.0, 0.0]),
            ExperienceCard(
                id=2, title="待确认", content="待确认内容", category="开头",
                source_type="manual", status="pending", created_by=1,
            ),
        ])
        await db.commit()

        with pytest.raises(ExperienceMergeError):
            await merge_experiences(
                db, [1, 2], surviving_id=1,
                title="x", content="y", category=None,
            )

        with pytest.raises(ExperienceMergeError):
            await merge_experiences(
                db, [1, 999], surviving_id=1,
                title="x", content="y", category=None,
            )

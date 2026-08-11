"""Phase 0.5 工程基线：对象权限、发布幂等和可恢复进度。"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.progress import ProgressStore
from app.models.creation import ContentCreation
from app.models.creation_publication import CreationPublication
from app.models.user import User
from app.services.creation_publication import (
    begin_creation_publication,
    fail_creation_publication,
    record_creation_publication,
)
from app.services.team_service import (
    can_access_creation,
    can_delete_creation,
    can_edit_creation,
    can_publish_creation,
)


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _QueuedSession:
    def __init__(self, *values):
        self.values = list(values)

    async def execute(self, _statement):
        return _ScalarResult(self.values.pop(0))


def _user(user_id: int, role: str = "user", *, active: bool = True) -> User:
    return User(
        id=user_id,
        username=f"user-{user_id}",
        role=role,
        is_active=active,
        is_superuser=False,
    )


def _creation(owner_id: int = 1) -> ContentCreation:
    return ContentCreation(id=10, user_id=owner_id, title="测试文章", status="draft")


@pytest.mark.asyncio
async def test_creation_permissions_distinguish_editor_and_viewer():
    creation = _creation()
    editor = _user(2, "employee")
    viewer = _user(3, "employee")

    assert await can_access_creation(_QueuedSession(None, "editor"), editor, creation)
    assert await can_edit_creation(_QueuedSession(None, "editor", "editor"), editor, creation)
    assert not await can_publish_creation(_QueuedSession(None, "editor"), editor, creation)

    assert await can_access_creation(_QueuedSession(None, "viewer"), viewer, creation)
    assert not await can_edit_creation(_QueuedSession(None, "viewer", "viewer"), viewer, creation)
    assert not await can_delete_creation(_QueuedSession(None, "viewer"), viewer, creation)


@pytest.mark.asyncio
async def test_creation_permissions_block_inactive_and_left_employee():
    creation = _creation()
    inactive = _user(2, "employee", active=False)
    left = _user(3, "employee")

    assert not await can_access_creation(_QueuedSession(), inactive, creation)
    assert not await can_access_creation(_QueuedSession("left"), left, creation)


@pytest.mark.asyncio
async def test_progress_store_async_snapshot_uses_same_owner_boundary():
    store = ProgressStore(redis_enabled=False)
    run_id = store.create_run(user_id=11)
    await store.push(run_id, {"event": "step_start", "data": {"step": 1, "agent": "writer"}})
    await store.push(run_id, {"event": "result", "data": {"creation_id": 10}})

    snapshot = await store.snapshot_async(run_id, user_id=11)
    assert snapshot["done"] is True
    assert snapshot["result"] == {"creation_id": 10}
    assert await store.snapshot_async(run_id, user_id=12) is None


@pytest.mark.asyncio
async def test_publication_record_is_idempotent_and_keeps_wechat_draft_state():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: User.metadata.create_all(
                sync_conn,
                tables=[User.__table__, ContentCreation.__table__, CreationPublication.__table__],
            )
        )

    async with session_factory() as db:
        db.add(User(id=1, username="owner", role="user", is_active=True))
        db.add(ContentCreation(id=10, user_id=1, title="测试文章", status="draft"))
        await db.commit()

        first_creation, first_publication, first_idempotent = await record_creation_publication(
            db,
            creation_id=10,
            initiated_by=1,
            platform="wechat_draft",
            operation="draft_upload",
            external_id="draft-1",
        )
        second_creation, second_publication, second_idempotent = await record_creation_publication(
            db,
            creation_id=10,
            initiated_by=1,
            platform="wechat_draft",
            operation="draft_upload",
            external_id="draft-1",
        )

        assert first_idempotent is False
        assert second_idempotent is True
        assert first_creation.status == "wechat_draft"
        assert second_creation.status == "wechat_draft"
        assert first_publication.id == second_publication.id
        assert await db.scalar(
            select(func.count()).select_from(CreationPublication)
        ) == 1

        db.add(ContentCreation(id=11, user_id=1, title="幂等文章", status="draft"))
        await db.commit()
        _, pending, first_claim = await begin_creation_publication(
            db,
            creation_id=11,
            initiated_by=1,
            platform="wechat_draft",
            operation="draft_upload",
            request_key="req-11",
        )
        _, same_pending, duplicate_claim = await begin_creation_publication(
            db,
            creation_id=11,
            initiated_by=1,
            platform="wechat_draft",
            operation="draft_upload",
            request_key="req-11",
        )
        assert first_claim is False
        assert duplicate_claim is True
        assert pending.id == same_pending.id
        assert pending.status == "pending"

        await fail_creation_publication(
            db,
            creation_id=11,
            initiated_by=1,
            platform="wechat_draft",
            operation="draft_upload",
            request_key="req-11",
            error_message="微信暂时不可用",
        )
        _, retried_pending, retry_claim = await begin_creation_publication(
            db,
            creation_id=11,
            initiated_by=1,
            platform="wechat_draft",
            operation="draft_upload",
            request_key="req-11",
        )
        assert retry_claim is False
        assert retried_pending.status == "pending"

    await engine.dispose()

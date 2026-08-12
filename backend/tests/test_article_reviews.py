"""团队协作文章复盘工作台测试。"""

import io

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.datastructures import Headers, UploadFile

from app.api.v1 import article_reviews as reviews_api
from app.core.progress import progress_store
from app.models.article_review import ArticleReview, ArticleReviewComment
from app.models.content_version import ExperienceCard
from app.models.employee_profile import EmployeeProfile
from app.models.user import User
from app.schemas.article_review import (
    ArticleReviewAnalysisUpdate,
    ArticleReviewCommentCreate,
    ArticleReviewPromote,
)
from app.services.article_review_service import (
    ArticleReviewAnalysisError,
    build_change_groups,
    normalize_article_review_analysis,
)


def _user(user_id: int, role: str = "employee") -> User:
    return User(
        id=user_id,
        username=f"review-user-{user_id}",
        full_name=f"复盘成员{user_id}",
        role=role,
        is_active=True,
        is_superuser=False,
    )


@pytest.fixture
async def review_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: User.metadata.create_all(
                sync_conn,
                tables=[
                    User.__table__,
                    EmployeeProfile.__table__,
                    ArticleReview.__table__,
                    ArticleReviewComment.__table__,
                    ExperienceCard.__table__,
                ],
            )
        )
    try:
        yield factory
    finally:
        await engine.dispose()


def _request() -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/api/v1/reviews",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("testclient", 1),
    })


def _upload(name: str, text: str) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(text.encode("utf-8")),
        filename=name,
        headers=Headers({"content-type": "text/plain"}),
    )


def test_change_groups_only_include_changes_and_mark_major_blocks():
    before = "标题\n\n" + ("旧段落。" * 40) + "\n\n保留段落"
    after = "标题\n\n" + ("新段落，补充了具体冲突和读者结果。" * 40) + "\n\n保留段落"
    result = build_change_groups(before, after)
    assert result["total_groups"] == 1
    assert result["major_group_count"] == 1
    assert result["groups"][0]["is_major"] is True
    assert result["groups"][0]["kind"] == "replace"


def test_analysis_normalization_requires_real_change_id():
    normalized = normalize_article_review_analysis({
        "summary": "强化开头",
        "key_changes": [{
            "group_id": "change-001",
            "what_changed": "把抽象判断换成具体冲突",
            "confidence": 0.8,
        }],
        "methodology_candidates": [{
            "title": "先给具体冲突",
            "rule": "开头先让读者看到真实冲突",
            "evidence_group_ids": ["change-001"],
        }],
    })
    assert normalized["key_changes"][0]["confidence"] == 0.8
    assert normalized["methodology_candidates"][0]["evidence_group_ids"] == ["change-001"]
    with pytest.raises(ArticleReviewAnalysisError):
        normalize_article_review_analysis({"open_questions": []})


@pytest.mark.asyncio
async def test_upload_queues_background_prepare_task(review_db, monkeypatch, tmp_path):
    employee = _user(1)
    monkeypatch.setattr(reviews_api, "enforce_rate_limit", lambda *args, **kwargs: _noop())

    async def fake_stage(*args, **kwargs):
        return (
            "改前.txt",
            str(tmp_path / "before.txt"),
            "改后.txt",
            str(tmp_path / "after.txt"),
        )

    queued = {}

    def fake_apply(*args, **kwargs):
        queued["args"] = args
        queued["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(reviews_api, "_stage_review_uploads", fake_stage)
    monkeypatch.setattr(reviews_api.prepare_article_review_task, "apply_async", fake_apply)
    async with review_db() as db:
        db.add(employee)
        await db.commit()
        result = await reviews_api.create_article_review(
            _request(),
            _upload("改前.txt", "开头冲突\n\n旧案例"),
            _upload("改后.txt", "开头冲突更具体\n\n新增真实案例"),
            "文章复盘测试",
            db,
            employee,
        )
        review = (await db.execute(select(ArticleReview))).scalar_one()
        assert result["data"]["task"]["status"] == "queued"
        assert result["data"]["task"]["task_id"] == queued["kwargs"]["task_id"]
        assert queued["kwargs"]["args"] == [review.id, review.progress_run_id]
        assert review.status == "processing"
        assert review.change_groups == []
        assert review.before_text == ""
        assert review.before_file_path.endswith("before.txt")


@pytest.mark.asyncio
async def test_progress_stream_emits_terminal_snapshot(review_db):
    employee = _user(1)
    run_id = progress_store.create_run(user_id=employee.id)
    await progress_store.push(run_id, {
        "event": "result",
        "data": {"status": "reviewing", "review_id": 1},
    })
    async with review_db() as db:
        db.add(employee)
        review = ArticleReview(
            title="流式复盘",
            before_filename="before.txt",
            after_filename="after.txt",
            before_text="旧",
            after_text="新",
            change_groups=[],
            status="reviewing",
            progress_run_id=run_id,
            created_by=employee.id,
        )
        db.add(review)
        await db.commit()
        await db.refresh(review)
        response = await reviews_api.stream_article_review_progress(review.id, db, employee)
        chunks = [chunk async for chunk in response.body_iterator]
    progress_store.cleanup(run_id)
    body = "".join(chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in chunks)
    assert "text/event-stream" in response.media_type
    assert '"done": true' in body
    assert '"status": "reviewing"' in body


@pytest.mark.asyncio
async def test_review_list_does_not_lazy_load_comments(review_db):
    """列表只返回摘要，不应因评论关系未请求而触发 MissingGreenlet。"""
    employee = _user(1)
    async with review_db() as db:
        db.add(employee)
        review = ArticleReview(
            title="列表懒加载回归",
            before_filename="before.txt",
            after_filename="after.txt",
            before_text="旧稿",
            after_text="新稿",
            change_groups=[],
            status="processing",
            created_by=employee.id,
        )
        db.add(review)
        await db.commit()

        result = await reviews_api.list_article_reviews(1, 50, None, None, db, employee)

    item = result["data"]["items"][0]
    assert item["id"] == review.id
    assert item["comments"] == []
    assert item["change_groups"] == []


@pytest.mark.asyncio
async def test_review_upload_reports_single_and_total_size_limits(monkeypatch):
    monkeypatch.setattr(reviews_api, "MAX_REVIEW_UPLOAD_SIZE", 10)
    monkeypatch.setattr(reviews_api, "MAX_REVIEW_FILES_SIZE", 15)

    accepted = await reviews_api._read_review_upload(_upload("ok.txt", "1234567890"))
    assert accepted[0] == "ok.txt"

    with pytest.raises(HTTPException) as single_error:
        await reviews_api._read_review_upload(_upload("large.txt", "12345678901"))
    assert single_error.value.status_code == 413
    assert single_error.value.detail["scope"] == "single_file"
    assert "实际" in single_error.value.detail["message"]

    with pytest.raises(HTTPException) as total_error:
        await reviews_api._stage_review_uploads(
            _upload("before.txt", "1234567890"),
            _upload("after.txt", "1234567890"),
        )
    assert total_error.value.status_code == 413
    assert total_error.value.detail["scope"] == "files_total"
    assert "本次请求文件总大小" in total_error.value.detail["message"]


@pytest.mark.asyncio
async def test_comment_update_and_promote_keep_review_trace(review_db, monkeypatch):
    employee = _user(1)
    monkeypatch.setattr(reviews_api, "enqueue_embedding", _fake_embedding)
    async with review_db() as db:
        db.add(employee)
        review = ArticleReview(
            title="复盘主题",
            before_filename="before.txt",
            after_filename="after.txt",
            before_text="旧",
            after_text="新",
            before_char_count=1,
            after_char_count=1,
            change_groups=[{
                "id": "change-001",
                "impact": "high",
                "is_major": True,
                "before": "旧",
                "after": "新",
                "before_block_count": 1,
                "after_block_count": 1,
            }],
            ai_analysis={
                "summary": "强化表达",
                "key_changes": [{
                    "group_id": "change-001",
                    "what_changed": "旧改成新",
                    "likely_reason": "更具体",
                    "effect": "更易理解",
                }],
                "methodology_candidates": [{
                    "title": "具体化表达",
                    "rule": "抽象判断需要落到具体结果",
                    "evidence_group_ids": ["change-001"],
                }],
            },
            status="reviewing",
            created_by=1,
        )
        db.add(review)
        await db.commit()
        await db.refresh(review)
        comment = await reviews_api.add_article_review_comment(
            review.id,
            ArticleReviewCommentCreate(change_group_id="change-001", body="这里的具体结果值得保留"),
            db,
            employee,
        )
        assert comment["data"]["comment"]["change_group_id"] == "change-001"
        updated = await reviews_api.update_article_review_analysis(
            review.id,
            ArticleReviewAnalysisUpdate(summary="人工确认：强化表达"),
            db,
            employee,
        )
        assert updated["data"]["review"]["ai_analysis"]["manually_edited"] is True
        promoted = await reviews_api.promote_article_review_methodology(
            review.id,
            ArticleReviewPromote(change_group_ids=["change-001"]),
            db,
            employee,
        )
        assert promoted["data"]["card"]["source_type"] == "review_feedback"
        assert promoted["data"]["card"]["version_pair"]["review_id"] == review.id
        stored = (await db.execute(select(ExperienceCard))).scalar_one()
        assert stored.version_pair["change_group_ids"] == ["change-001"]
        assert review.id in (await db.get(ArticleReview, review.id)).promoted_card_ids


@pytest.mark.asyncio
async def test_normal_user_cannot_open_review(review_db):
    normal = _user(2, "user")
    async with review_db() as db:
        db.add(normal)
        await db.commit()
        with pytest.raises(HTTPException) as error:
            await reviews_api.list_article_reviews(1, 20, None, None, db, normal)
        assert error.value.status_code == 403


async def _noop():
    return None


async def _fake_embedding(card, db):
    return {"status": "failed", "task_id": "embedding-test"}

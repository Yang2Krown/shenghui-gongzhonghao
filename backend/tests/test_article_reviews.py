"""团队协作文章复盘工作台测试。"""

import io

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.datastructures import Headers, UploadFile

from app.api.v1 import article_reviews as reviews_api
from app.core.progress import progress_store
from app.models.article_review import (
    ArticleReview,
    ArticleReviewChange,
    ArticleReviewComment,
    ArticleReviewExperienceSource,
    ArticleReviewMethodologyCandidate,
    ArticleReviewReorderEvent,
    ArticleReviewRun,
    ArticleReviewSemanticBlock,
    ArticleReviewStage,
)
from app.models.content_version import ExperienceCard
from app.models.employee_profile import EmployeeProfile
from app.models.user import User
from app.schemas.article_review import (
    ArticleReviewAnalysisUpdate,
    ArticleReviewCommentCreate,
    ArticleReviewCommentUpdate,
    ArticleReviewPromote,
)
from app.services.article_review_service import (
    ArticleReviewAnalysisError,
    build_change_groups,
    build_semantic_blocks,
    normalize_article_review_analysis,
)
from app.services.article_review_workflow import (
    create_run_with_stages,
    load_workflow_entities,
    persist_diff_artifacts,
)
from app.tasks import article_review_tasks as review_tasks


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
                    ArticleReviewRun.__table__,
                    ArticleReviewStage.__table__,
                    ArticleReviewSemanticBlock.__table__,
                    ArticleReviewChange.__table__,
                    ArticleReviewReorderEvent.__table__,
                    ArticleReviewMethodologyCandidate.__table__,
                    ArticleReviewExperienceSource.__table__,
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


def test_semantic_blocks_merge_short_lines_and_keep_source_offsets():
    text = "第一句先说明冲突。\n然后补充背景。\n\n最后给出结论。"
    blocks = build_semantic_blocks(text, side="before")
    assert len(blocks) == 2
    assert blocks[0]["raw_block_count"] == 2
    assert blocks[0]["text"] == "第一句先说明冲突。\n然后补充背景。"
    assert text[blocks[0]["start_offset"]:blocks[0]["end_offset"]] == blocks[0]["text"]
    assert blocks[0]["source_line_start"] == 1
    assert blocks[0]["source_line_end"] == 2
    assert blocks[0]["stable_id"].startswith("sb-b-")


def test_semantic_blocks_do_not_split_one_sentence_per_line_or_keep_version_noise():
    text = (
        "1.0\n"
        "前几天Seedance 2.5上线后，我本来没有抱太多的期待。\n"
        "毕竟不是一个跳跃式的版本更新。\n"
        "那几天我还都沉浸在测试H3当中，测了一个又一个案例。\n"
        "\n"
        "但是就在我沉浸于H3之中的时候，接连好几个读者反馈。"
    )
    blocks = build_semantic_blocks(text, side="before")

    assert all(block["text"] != "1.0" for block in blocks)
    assert len(blocks) == 2
    assert blocks[0]["source_line_start"] == 2
    assert blocks[0]["source_line_end"] == 4
    assert blocks[0]["raw_block_count"] == 3


def test_semantic_diff_distinguishes_minor_rewrite_addition_and_reorder():
    minor = build_change_groups("我们要做的事情。", "我们要做了事情！")
    assert [item["change_type"] for item in minor["groups"]] == ["minor_edit"]
    assert minor["groups"][0]["is_major"] is False

    addition = build_change_groups(
        "开头说明。\n正文观点。",
        "开头说明。\n新增一个重要案例，说明用户如何从问题走向结果。\n正文观点。",
    )
    assert any(item["change_type"] == "addition" for item in addition["groups"])

    reorder = build_change_groups(
        "第一部分先讲背景。\n第二部分再讲方法。\n第三部分最后总结。",
        "第二部分再讲方法。\n第一部分先讲背景。\n第三部分最后总结。",
    )
    assert reorder["reorder_events"]
    assert {item["change_type"] for item in reorder["groups"]} == {"reorder"}

    rewrite = build_change_groups(
        "这是原稿中的一段完整论证，包含背景、问题、证据和结论，用来解释为什么团队应该改变当前的工作方式。" * 3,
        "改稿重新从用户实际体验出发，先呈现冲突，再用新的案例说明改法能够降低沟通成本，最后给出可执行的协作步骤和验收标准。" * 3,
    )
    assert [item["change_type"] for item in rewrite["groups"]] == ["rewrite"]
    assert rewrite["groups"][0]["is_major"] is True


@pytest.mark.asyncio
async def test_workflow_persists_stages_blocks_changes_and_reorders(review_db):
    employee = _user(1)
    async with review_db() as db:
        db.add(employee)
        review = ArticleReview(
            title="规范化工作流",
            before_filename="before.txt",
            after_filename="after.txt",
            before_text="第一部分先讲背景。\n第二部分再讲方法。",
            after_text="第二部分再讲方法。\n第一部分先讲背景。",
            before_char_count=20,
            after_char_count=20,
            change_groups=[],
            status="processing",
            progress_run_id="workflow-run-1",
            created_by=employee.id,
        )
        db.add(review)
        await db.commit()
        await db.refresh(review)
        run = await create_run_with_stages(
            db,
            review,
            run_id="workflow-run-1",
            created_by=employee.id,
        )
        diff = build_change_groups(review.before_text, review.after_text)
        review.change_groups = diff["groups"]
        await persist_diff_artifacts(db, review, run, diff)
        await db.commit()

        payload = await load_workflow_entities(db, review.id)

    assert payload["run"]["run_id"] == "workflow-run-1"
    assert [stage["stage_key"] for stage in payload["run"]["stages"]] == [
        "parse", "semantic_segmentation", "semantic_alignment", "ai_review", "methodology",
    ]
    assert len(payload["blocks"]) == 4
    assert payload["changes"]
    assert payload["reorder_events"]


@pytest.mark.asyncio
async def test_prepare_task_persists_parse_and_waiting_semantic_stage(review_db, monkeypatch, tmp_path):
    employee = _user(1)
    before_path = tmp_path / "before.txt"
    after_path = tmp_path / "after.txt"
    before_path.write_text("第一部分先讲背景。\n第二部分再讲方法。", encoding="utf-8")
    after_path.write_text("第二部分再讲方法。\n第一部分先讲背景。", encoding="utf-8")
    monkeypatch.setattr(review_tasks, "AsyncSessionLocal", review_db)
    monkeypatch.setattr(review_tasks.settings, "UPLOAD_DIR", str(tmp_path))

    async with review_db() as db:
        db.add(employee)
        review = ArticleReview(
            title="异步解析阶段",
            before_filename="before.txt",
            after_filename="after.txt",
            before_file_path=str(before_path),
            after_file_path=str(after_path),
            before_text="",
            after_text="",
            change_groups=[],
            status="processing",
            progress_run_id="prepare-run-1",
            analysis_task_id="prepare-task-1",
            created_by=employee.id,
        )
        db.add(review)
        await db.commit()
        await db.refresh(review)
        await create_run_with_stages(
            db,
            review,
            run_id="prepare-run-1",
            created_by=employee.id,
        )
        await db.commit()
        review_id = review.id

    result = await review_tasks._run_article_review_prepare(
        review_id,
        "prepare-run-1",
        "prepare-task-1",
    )

    async with review_db() as db:
        payload = await load_workflow_entities(db, review_id)
        stored = await db.get(ArticleReview, review_id)
    statuses = {stage["stage_key"]: stage["status"] for stage in payload["run"]["stages"]}
    assert result["status"] == "waiting_confirmation"
    assert statuses["parse"] == "succeeded"
    assert statuses["semantic_segmentation"] == "awaiting_confirmation"
    assert statuses["semantic_alignment"] == "blocked"
    assert len(payload["blocks"]) == 4
    assert stored.before_file_path is None
    assert stored.after_file_path is None


@pytest.mark.asyncio
async def test_semantic_segmentation_retry_stops_for_human_confirmation(review_db, monkeypatch):
    employee = _user(1)
    monkeypatch.setattr(review_tasks, "AsyncSessionLocal", review_db)
    async with review_db() as db:
        db.add(employee)
        review = ArticleReview(
            title="分段阶段重试",
            before_filename="before.txt",
            after_filename="after.txt",
            before_text="第一部分先讲背景。\n第二部分再讲方法。",
            after_text="第二部分再讲方法。\n第一部分先讲背景。",
            before_char_count=20,
            after_char_count=20,
            change_groups=[],
            status="failed",
            progress_run_id="segment-retry-1",
            analysis_task_id="segment-task-1",
            created_by=employee.id,
        )
        db.add(review)
        await db.commit()
        await db.refresh(review)
        await create_run_with_stages(
            db,
            review,
            run_id="segment-retry-1",
            created_by=employee.id,
        )
        await db.commit()
        review_id = review.id

    result = await review_tasks._run_article_review_semantic_segmentation(
        review_id,
        "segment-retry-1",
        "segment-task-1",
    )

    async with review_db() as db:
        payload = await load_workflow_entities(db, review_id)
        stored = await db.get(ArticleReview, review_id)
    statuses = {stage["stage_key"]: stage["status"] for stage in payload["run"]["stages"]}
    assert result["status"] == "waiting_confirmation"
    assert statuses["semantic_segmentation"] == "awaiting_confirmation"
    assert statuses["semantic_alignment"] == "blocked"
    assert stored.status == "processing"
    assert len(payload["blocks"]) == 4


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
async def test_progress_store_keeps_stage_partial_result_and_resumes_after_waiting():
    run_id = progress_store.create_run(user_id=1)
    try:
        await progress_store.push(run_id, {
            "event": "stage_waiting",
            "data": {"stage": "semantic_segmentation", "message": "等待确认语义块"},
        })
        waiting = progress_store.snapshot(run_id, user_id=1)
        assert waiting["done"] is True
        assert waiting["stage"] == "semantic_segmentation"

        await progress_store.push(run_id, {
            "event": "step_start",
            "data": {"step": 3, "stage": "semantic_alignment", "action": "正在对齐"},
        })
        await progress_store.push(run_id, {
            "event": "partial_result",
            "data": {"stage": "semantic_alignment", "major_group_count": 2},
        })
        resumed = progress_store.snapshot(run_id, user_id=1)
        assert resumed["done"] is False
        assert resumed["stage"] == "semantic_alignment"
        assert resumed["partial_result"]["major_group_count"] == 2
        assert resumed["last_event_id"] == 3
    finally:
        progress_store.cleanup(run_id)


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
async def test_review_delete_requires_owner_and_cleans_workflow_entities(review_db):
    employee = _user(1)
    other_employee = _user(2)
    async with review_db() as db:
        db.add_all([employee, other_employee])
        review = ArticleReview(
            title="待删除复盘",
            before_filename="before.txt",
            after_filename="after.txt",
            before_text="旧稿",
            after_text="新稿",
            change_groups=[],
            status="processing",
            progress_run_id="delete-review-run",
            created_by=employee.id,
        )
        db.add(review)
        await db.commit()
        await db.refresh(review)
        run = await create_run_with_stages(
            db,
            review,
            run_id="delete-review-run",
            created_by=employee.id,
        )
        block = ArticleReviewSemanticBlock(
            review_id=review.id,
            review_run_id=run.id,
            stable_id="sb-b-delete-01",
            side="before",
            ordinal=1,
            text="旧稿",
            normalized_text="旧稿",
        )
        db.add(block)
        db.add(ArticleReviewChange(
            review_id=review.id,
            review_run_id=run.id,
            stable_id="change-delete-01",
            ordinal=1,
            change_type="rewrite",
            before_block_ids=[block.stable_id],
            after_block_ids=[],
            before_text="旧稿",
            after_text="新稿",
        ))
        db.add(ArticleReviewReorderEvent(
            review_id=review.id,
            review_run_id=run.id,
            stable_id="reorder-delete-01",
            ordinal=1,
            before_block_ids=[block.stable_id],
            after_block_ids=[],
        ))
        db.add(ArticleReviewMethodologyCandidate(
            review_id=review.id,
            review_run_id=run.id,
            title="删除测试方法",
            rule="删除前清理所有运行产物",
            evidence_change_ids=["change-delete-01"],
        ))
        db.add(ArticleReviewComment(
            review_id=review.id,
            change_group_id="change-delete-01",
            body="删除测试评论",
            author_id=employee.id,
        ))
        await db.commit()
        review_id = review.id

        with pytest.raises(HTTPException) as permission_error:
            await reviews_api.delete_article_review(review_id, db, other_employee)
        assert permission_error.value.status_code == 403

        result = await reviews_api.delete_article_review(review_id, db, employee)
        assert result["data"] == {"review_id": review_id}
        assert await db.get(ArticleReview, review_id) is None
        assert not (await db.execute(select(ArticleReviewRun).where(ArticleReviewRun.review_id == review_id))).scalars().all()
        assert not (await db.execute(select(ArticleReviewSemanticBlock).where(ArticleReviewSemanticBlock.review_id == review_id))).scalars().all()
        assert not (await db.execute(select(ArticleReviewChange).where(ArticleReviewChange.review_id == review_id))).scalars().all()
        assert not (await db.execute(select(ArticleReviewReorderEvent).where(ArticleReviewReorderEvent.review_id == review_id))).scalars().all()
        assert not (await db.execute(select(ArticleReviewMethodologyCandidate).where(ArticleReviewMethodologyCandidate.review_id == review_id))).scalars().all()
        assert not (await db.execute(select(ArticleReviewComment).where(ArticleReviewComment.review_id == review_id))).scalars().all()


@pytest.mark.asyncio
async def test_review_delete_keeps_source_trace_for_promoted_experience(review_db):
    employee = _user(1)
    async with review_db() as db:
        db.add(employee)
        card = ExperienceCard(
            title="已沉淀经验",
            content="保留来源",
            source_type="review_feedback",
            created_by=employee.id,
        )
        db.add(card)
        await db.flush()
        review = ArticleReview(
            title="已沉淀复盘",
            before_filename="before.txt",
            after_filename="after.txt",
            before_text="旧稿",
            after_text="新稿",
            change_groups=[],
            status="reviewing",
            promoted_card_ids=[card.id],
            created_by=employee.id,
        )
        db.add(review)
        await db.flush()
        source = ArticleReviewExperienceSource(
            experience_card_id=card.id,
            review_id=review.id,
            comment_ids=[],
            confirmed_conclusion="保留来源追溯",
            confirmed_by=employee.id,
        )
        db.add(source)
        await db.commit()

        with pytest.raises(HTTPException) as error:
            await reviews_api.delete_article_review(review.id, db, employee)
        assert error.value.status_code == 409
        assert error.value.detail["code"] == "review_has_experience_sources"
        assert await db.get(ArticleReview, review.id) is not None


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
        edited_comment = await reviews_api.update_article_review_comment(
            review.id,
            comment["data"]["comment"]["id"],
            ArticleReviewCommentUpdate(body="这里的具体结果值得保留，团队确认后可复用", resolved=True, processing_status="accepted"),
            db,
            employee,
        )
        assert edited_comment["data"]["comment"]["edit_status"] == "edited"
        assert edited_comment["data"]["comment"]["processing_status"] == "accepted"
        other_employee = _user(2)
        db.add(other_employee)
        await db.commit()
        with pytest.raises(HTTPException) as comment_permission:
            await reviews_api.update_article_review_comment(
                review.id,
                comment["data"]["comment"]["id"],
                ArticleReviewCommentUpdate(resolved=False),
                db,
                other_employee,
            )
        assert comment_permission.value.status_code == 403
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
        repeated = await reviews_api.promote_article_review_methodology(
            review.id,
            ArticleReviewPromote(change_group_ids=["change-001"]),
            db,
            employee,
        )
        assert repeated["data"]["idempotent"] is True
        stored = (await db.execute(select(ExperienceCard))).scalar_one()
        assert stored.version_pair["change_group_ids"] == ["change-001"]
        sources = (await db.execute(select(ArticleReviewExperienceSource))).scalars().all()
        assert len(sources) == 1
        assert sources[0].comment_ids == [comment["data"]["comment"]["id"]]
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

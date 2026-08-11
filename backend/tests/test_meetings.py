"""Phase 1b 会议方法论沉淀测试。"""

import json
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1 import meetings as meetings_api
from app.api.v1.meetings import (
    _require_meeting_access,
    create_meeting,
    list_meetings,
    link_meeting_suggestion,
    meeting_summary,
    meeting_stats,
    update_meeting_synthesis,
    update_meeting_suggestion,
)
from app.models.article_member import ArticleMember
from app.models.creation import ContentCreation
from app.models.meeting import Meeting, MeetingSuggestion, MeetingSynthesis
from app.models.meeting_methodology import MeetingMethodologyCluster, MeetingMethodologySource
from app.models.employee_profile import EmployeeProfile
from app.models.user import User
from app.schemas.meeting import (
    MeetingCreate,
    MeetingSuggestionLinkRequest,
    MeetingSuggestionUpdate,
    MeetingSynthesisUpdate,
)
from app.services.meeting_synthesis import MeetingSynthesisError, extract_meeting_synthesis
from app.services.meeting_methodology_dedup import prune_orphan_methodology_clusters, sync_methodology_clusters
from app.tasks import meeting_tasks
from app.services.llm.llm_client import ChatResult


class FakeLLM:
    def __init__(self, text: str):
        self.text = text
        self.calls = 0

    async def chat(self, messages, **kwargs):
        self.calls += 1
        return ChatResult(text=self.text)


def _user(user_id: int, role: str = "user") -> User:
    return User(
        id=user_id,
        username=f"user-{user_id}",
        full_name=f"用户{user_id}",
        role=role,
        is_active=True,
        is_superuser=False,
    )


@pytest.fixture
async def meeting_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: User.metadata.create_all(
                sync_conn,
                tables=[
                    User.__table__,
                    EmployeeProfile.__table__,
                    ContentCreation.__table__,
                    Meeting.__table__,
                    MeetingSynthesis.__table__,
                    MeetingMethodologyCluster.__table__,
                    MeetingMethodologySource.__table__,
                    MeetingSuggestion.__table__,
                    ArticleMember.__table__,
                ],
            )
        )
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def disable_external_meeting_embedding(monkeypatch):
    """会议单测不访问外部 embedding 服务；语义行为由显式 FakeEmbedder 覆盖。"""
    async def no_embedding(texts):
        return [None for _ in texts]

    monkeypatch.setattr(
        "app.services.meeting_methodology_dedup.embedding_service.embed_batch",
        no_embedding,
    )


@pytest.mark.asyncio
async def test_meeting_synthesis_accepts_structured_methodology_object():
    payload = {
        "summary": "先把文章结构和判断标准对齐，再开始写作。",
        "methodology": [
            {
                "title": "先串后写",
                "rule": "先想清楚钩子如何自然过渡到产品，再动笔。",
                "rationale": "减少返工。",
                "example": "Seedance 2.5 评测先确定切入点。",
                "evidence": "会议复盘认为原版本上下文断裂。",
            }
        ],
        "checklist": [{"item": "钩子是否撑得起标题和篇幅", "description": "动笔前先确认", "when_to_use": "每篇文章开始前"}],
        "decisions": [{"decision": "功能排序要与标题主角对齐", "context": "避免重点能力被放到最后。"}],
        "disagreements": [{"topic": "爆款短剧是否作为开头", "views": ["保留引流", "上下文和选题冲突"], "current_position": "当前版本先去掉。"}],
        "open_questions": [{"question": "结尾如何形成互动点", "context": "现有结尾空泛。", "next_step": "收集高互动结尾样本。"}],
        "follow_ups": [{"content": "每篇文章动笔前按清单和团队对齐", "owner": None, "deadline": None}],
    }
    fake = FakeLLM(json.dumps(payload, ensure_ascii=False))

    result = await extract_meeting_synthesis("会议讨论写作方法。", "周会", llm_client=fake)

    assert fake.calls == 1
    assert result["summary"] == payload["summary"]
    assert result["methodology"][0]["title"] == "先串后写"
    assert result["checklist"][0]["item"] == "钩子是否撑得起标题和篇幅"
    assert result["raw_json"]["raw_output"]


@pytest.mark.asyncio
async def test_methodology_dedup_merges_semantically_similar_items_and_keeps_sources(meeting_db):
    class FakeEmbedder:
        async def embed_batch(self, texts):
            return [[1.0, 0.0] for _ in texts]

    async with meeting_db() as db:
        db.add_all([
            Meeting(
                id=70,
                title="第一次写作复盘",
                meeting_at=datetime(2026, 8, 1, 10),
                raw_text="原文一",
                status="ready",
                source_kind="pasted_text",
                created_by=1,
            ),
            Meeting(
                id=71,
                title="第二次写作复盘",
                meeting_at=datetime(2026, 8, 8, 10),
                raw_text="原文二",
                status="ready",
                source_kind="pasted_text",
                created_by=1,
            ),
        ])
        await db.commit()

        first = await sync_methodology_clusters(
            db,
            70,
            {"methodology": [{"title": "先串后写", "rule": "动笔前先把钩子和产品串成完整故事"}], "checklist": []},
            embedder=FakeEmbedder(),
            judge_borderline=False,
        )
        second = await sync_methodology_clusters(
            db,
            71,
            {"methodology": [{"title": "动笔前先对齐", "rule": "写之前先把切入点和产品功能串起来"}], "checklist": []},
            embedder=FakeEmbedder(),
            judge_borderline=False,
        )
        await db.commit()

        assert first["new_clusters"] == 1
        assert second["merged"] == 1
        clusters = (await db.scalars(select(MeetingMethodologyCluster))).all()
        sources = (await db.scalars(select(MeetingMethodologySource).order_by(MeetingMethodologySource.id))).all()
        assert len(clusters) == 1
        assert clusters[0].source_count == 2
        assert len(sources) == 2
        assert {source.meeting_id for source in sources} == {70, 71}
        assert sources[1].match_kind == "embedding"


@pytest.mark.asyncio
async def test_methodology_dedup_is_idempotent_for_same_meeting(meeting_db):
    class FakeEmbedder:
        async def embed_batch(self, texts):
            return [[1.0, 0.0] for _ in texts]

    payload = {"methodology": [{"title": "先串后写", "rule": "先确定钩子和产品如何衔接"}], "checklist": []}
    async with meeting_db() as db:
        db.add(Meeting(
            id=72,
            title="幂等会议",
            meeting_at=datetime(2026, 8, 9, 10),
            raw_text="原文",
            status="ready",
            source_kind="pasted_text",
            created_by=1,
        ))
        await db.commit()
        first = await sync_methodology_clusters(db, 72, payload, embedder=FakeEmbedder(), judge_borderline=False)
        second = await sync_methodology_clusters(db, 72, payload, embedder=FakeEmbedder(), judge_borderline=False)
        await db.commit()

        assert first["source_count"] == 1
        assert second["source_count"] == 0
        assert await db.scalar(select(MeetingMethodologyCluster.source_count)) == 1
        assert await db.scalar(select(MeetingMethodologySource.meeting_id)) == 72
        assert len((await db.scalars(select(MeetingMethodologySource))).all()) == 1


@pytest.mark.asyncio
async def test_methodology_dedup_uses_llm_for_borderline_similarity(meeting_db):
    class FakeEmbedder:
        def __init__(self):
            self.calls = 0

        async def embed_batch(self, texts):
            self.calls += 1
            if self.calls == 1:
                return [[1.0, 0.0] for _ in texts]
            return [[0.86, 0.51] for _ in texts]

    class FakeJudge:
        async def chat(self, messages, **kwargs):
            return ChatResult(
                text='{"same_principle":true,"confidence":0.91}',
                parsed={"same_principle": True, "confidence": 0.91},
            )

    async with meeting_db() as db:
        db.add_all([
            Meeting(
                id=73,
                title="边界会议一",
                meeting_at=datetime(2026, 8, 1, 10),
                raw_text="原文一",
                status="ready",
                source_kind="pasted_text",
                created_by=1,
            ),
            Meeting(
                id=74,
                title="边界会议二",
                meeting_at=datetime(2026, 8, 8, 10),
                raw_text="原文二",
                status="ready",
                source_kind="pasted_text",
                created_by=1,
            ),
        ])
        await db.commit()
        embedder = FakeEmbedder()
        await sync_methodology_clusters(
            db,
            73,
            {"methodology": [{"title": "先串后写", "rule": "先把文章路线跑通"}], "checklist": []},
            embedder=embedder,
            judge_borderline=False,
        )
        result = await sync_methodology_clusters(
            db,
            74,
            {"methodology": [{"title": "动笔前先对齐", "rule": "先确认文章结构再写"}], "checklist": []},
            embedder=embedder,
            llm_client=FakeJudge(),
        )
        assert result["merged"] == 1
        assert result["reviewed"] == 1
        source = (await db.scalars(
            select(MeetingMethodologySource).where(MeetingMethodologySource.meeting_id == 74)
        )).one()
        assert source.match_kind == "llm"


@pytest.mark.asyncio
async def test_meeting_synthesis_invalid_json_raises_business_error():
    with pytest.raises(MeetingSynthesisError):
        await extract_meeting_synthesis("会议纪要", "周会", llm_client=FakeLLM("这不是 JSON"))


@pytest.mark.asyncio
async def test_meeting_synthesis_repairs_truncated_json_object():
    result = await extract_meeting_synthesis(
        "会议纪要",
        "周会",
        llm_client=FakeLLM('{"summary":"保留完整结论","methodology":[{"title":"先串后写","rule":"先想清楚再写"'),
    )
    assert result["summary"] == "保留完整结论"
    assert result["parse_status"] == "repaired"


@pytest.mark.asyncio
async def test_meeting_access_allows_employee_admin_and_blocks_normal_user(meeting_db):
    async with meeting_db() as db:
        employee = _user(1, "employee")
        admin = _user(2, "admin")
        normal = _user(3, "user")
        assert await _require_meeting_access(db, employee) is None
        assert await _require_meeting_access(db, admin) is None
        with pytest.raises(HTTPException) as exc_info:
            await _require_meeting_access(db, normal)
        assert exc_info.value.status_code == 403
        with pytest.raises(HTTPException) as api_exc:
            await list_meetings(
                page=1,
                page_size=20,
                keyword=None,
                status=None,
                start_at=None,
                end_at=None,
                meeting_at_from=None,
                meeting_at_to=None,
                db=db,
                current_user=normal,
            )
        assert api_exc.value.status_code == 403


@pytest.mark.asyncio
async def test_meeting_create_and_list_api_return_task_and_filters(meeting_db, monkeypatch):
    async def fake_enqueue(db, meeting):
        return {
            "task_id": "task-api-1",
            "run_id": "run-api-1",
            "status": "queued",
            "deduplicated": False,
        }

    monkeypatch.setattr(meetings_api, "_enqueue_extraction", fake_enqueue)
    async with meeting_db() as db:
        employee = _user(1, "employee")
        db.add(employee)
        await db.commit()

        created = await create_meeting(
            MeetingCreate(
                title="API 周会",
                meeting_at=datetime(2026, 8, 11, 10),
                raw_text="下周发布案例文章",
            ),
            db,
            employee,
        )
        assert created["data"]["task"]["task_id"] == "task-api-1"
        assert created["data"]["meeting"]["status"] == "extracting"

        listed = await list_meetings(
            page=1,
            page_size=20,
            keyword="API",
            status="extracting",
            start_at=None,
            end_at=None,
            meeting_at_from=None,
            meeting_at_to=None,
            db=db,
            current_user=employee,
        )
        assert listed["data"]["total"] == 1
        assert listed["data"]["items"][0]["title"] == "API 周会"


@pytest.mark.asyncio
async def test_duplicate_task_does_not_duplicate_suggestions(meeting_db, monkeypatch):
    calls = []

    async def fake_synthesis(*args, **kwargs):
        calls.append(args)
        return {
            "summary": "会议明确先对齐写作结构。",
            "methodology": [{"title": "先串后写", "rule": "先想清楚再动笔", "rationale": None, "example": None, "evidence": None}],
            "checklist": [{"item": "先对齐钩子", "description": None, "when_to_use": None}],
            "decisions": [], "disagreements": [], "open_questions": [], "follow_ups": [],
            "raw_json": {"raw_output": "{}"}, "parse_status": "parsed",
        }

    monkeypatch.setattr(meeting_tasks, "extract_meeting_synthesis", fake_synthesis)

    async with meeting_db() as db:
        db.add(_user(1, "employee"))
        meeting = Meeting(
            id=10,
            title="周会",
            meeting_at=datetime(2026, 8, 11, 10),
            raw_text="下周发布案例文章",
            status="extracting",
            source_kind="pasted_text",
            created_by=1,
        )
        db.add(meeting)
        await db.commit()

        # 直接替换任务模块使用的会话工厂，验证真实异步任务逻辑。
        monkeypatch.setattr(meeting_tasks, "AsyncSessionLocal", meeting_db)
        first = await meeting_tasks._run_meeting_extraction(10, None, "task-1")
        second = await meeting_tasks._run_meeting_extraction(10, None, "task-2")

        assert first["status"] == "ready"
        assert second["status"] == "skipped"
        assert len(calls) == 1
        async with meeting_db() as verify_db:
            synthesis = (await verify_db.execute(
                select(MeetingSynthesis).where(MeetingSynthesis.meeting_id == 10)
            )).scalar_one()
            assert len(synthesis.methodology) == 1
            suggestions = (await verify_db.execute(
                select(MeetingSuggestion).where(MeetingSuggestion.meeting_id == 10)
            )).scalars().all()
            assert suggestions == []


@pytest.mark.asyncio
async def test_reextract_keeps_manual_suggestion_and_raw_json(meeting_db, monkeypatch):
    async def fake_synthesis(*args, **kwargs):
        return {
            "summary": "新一轮摘要不应覆盖人工沉淀。",
            "methodology": [{"title": "新方法", "rule": "新规则", "rationale": None, "example": None, "evidence": None}],
            "checklist": [], "decisions": [], "disagreements": [], "open_questions": [], "follow_ups": [],
            "raw_json": {"raw_output": "new-output"}, "parse_status": "parsed",
        }

    monkeypatch.setattr(meeting_tasks, "extract_meeting_synthesis", fake_synthesis)

    async with meeting_db() as db:
        db.add(_user(1, "employee"))
        meeting = Meeting(
            id=11,
            title="周会",
            meeting_at=datetime(2026, 8, 11, 10),
            raw_text="保留人工改过的行动，新增另一条行动",
            status="extracting",
            source_kind="pasted_text",
            created_by=1,
        )
        db.add(meeting)
        await db.flush()
        db.add(MeetingSuggestion(
            id=101,
            meeting_id=11,
            content="保留人工改过的行动（人工确认版）",
            category="流程",
            priority="P0",
            status="adopted",
            is_manually_edited=True,
            raw_json={"source": "manual"},
        ))
        db.add(MeetingSynthesis(
            meeting_id=11,
            summary="人工确认的摘要",
            methodology=[{"title": "人工方法", "rule": "保留这条"}],
            is_manually_edited=True,
            raw_json={"source": "manual"},
        ))
        await db.commit()
        monkeypatch.setattr(meeting_tasks, "AsyncSessionLocal", meeting_db)

        result = await meeting_tasks._run_meeting_extraction(11, None, "task-11")
        assert result["status"] == "ready"
        async with meeting_db() as verify_db:
            rows = (await verify_db.execute(
                select(MeetingSuggestion).where(MeetingSuggestion.meeting_id == 11).order_by(MeetingSuggestion.id)
            )).scalars().all()
            assert len(rows) == 1
            assert rows[0].status == "adopted"
            assert rows[0].raw_json == {"source": "manual"}
            synthesis = (await verify_db.execute(
                select(MeetingSynthesis).where(MeetingSynthesis.meeting_id == 11)
            )).scalar_one()
            assert synthesis.summary == "人工确认的摘要"
            assert synthesis.methodology[0]["title"] == "人工方法"
            assert synthesis.raw_json == {"raw_output": "new-output"}


@pytest.mark.asyncio
async def test_suggestion_state_machine_reject_reason_and_done_closed_at(meeting_db):
    async with meeting_db() as db:
        employee = _user(1, "employee")
        db.add(employee)
        meeting = Meeting(
            id=20,
            title="状态机会议",
            meeting_at=datetime(2026, 8, 10, 10),
            raw_text="行动",
            status="ready",
            source_kind="pasted_text",
            created_by=1,
        )
        suggestion = MeetingSuggestion(
            id=201,
            meeting_id=20,
            content="完成行动",
            category="流程",
            priority="P1",
            status="proposed",
        )
        db.add_all([meeting, suggestion])
        await db.commit()

        with pytest.raises(HTTPException) as invalid:
            await update_meeting_suggestion(
                201,
                MeetingSuggestionUpdate(status="done"),
                db,
                employee,
            )
        assert invalid.value.status_code == 400

        with pytest.raises(HTTPException) as no_reason:
            await update_meeting_suggestion(
                201,
                MeetingSuggestionUpdate(status="rejected"),
                db,
                employee,
            )
        assert no_reason.value.status_code == 400

        await update_meeting_suggestion(
            201,
            MeetingSuggestionUpdate(status="adopted"),
            db,
            employee,
        )
        await update_meeting_suggestion(
            201,
            MeetingSuggestionUpdate(status="in_progress"),
            db,
            employee,
        )
        response = await update_meeting_suggestion(
            201,
            MeetingSuggestionUpdate(status="done"),
            db,
            employee,
        )
        assert response["data"]["closed_at"] is not None

        with pytest.raises(HTTPException):
            await update_meeting_suggestion(
                201,
                MeetingSuggestionUpdate(status="proposed"),
                db,
                employee,
            )


@pytest.mark.asyncio
async def test_link_reuses_article_permission(meeting_db):
    async with meeting_db() as db:
        employee = _user(1, "employee")
        owner = _user(2, "user")
        db.add_all([employee, owner])
        meeting = Meeting(
            id=30,
            title="文章关联会议",
            meeting_at=datetime(2026, 8, 10, 10),
            raw_text="关联文章",
            status="ready",
            source_kind="pasted_text",
            created_by=1,
        )
        suggestion = MeetingSuggestion(
            id=301,
            meeting_id=30,
            content="修改文章",
            category="写作",
            priority="P1",
            status="proposed",
        )
        creation = ContentCreation(id=302, user_id=2, title="私有文章", status="draft")
        db.add_all([meeting, suggestion, creation])
        await db.commit()

        with pytest.raises(HTTPException) as forbidden:
            await link_meeting_suggestion(
                301,
                MeetingSuggestionLinkRequest(creation_id=302),
                db,
                employee,
            )
        assert forbidden.value.status_code == 403

        db.add(ArticleMember(creation_id=302, user_id=1, role="viewer", granted_by=2))
        await db.commit()
        linked = await link_meeting_suggestion(
            301,
            MeetingSuggestionLinkRequest(creation_id=302),
            db,
            employee,
        )
        assert linked["data"]["related_creation_id"] == 302


@pytest.mark.asyncio
async def test_stats_zero_denominators_return_zero(meeting_db):
    async with meeting_db() as db:
        employee = _user(1, "employee")
        db.add(employee)
        await db.commit()

        response = await meeting_stats(None, None, db, employee)
        data = response["data"]
        assert data["total_meetings"] == 0
        assert data["total_methodology"] == 0
        assert data["total_checklist"] == 0
        assert data["total_open_questions"] == 0
        assert data["by_week"] == []
        assert data["by_meeting"] == []


@pytest.mark.asyncio
async def test_stats_non_empty_groups_methodology(meeting_db):
    async with meeting_db() as db:
        employee = _user(1, "employee")
        db.add(employee)
        meeting = Meeting(
            id=40,
            title="看板会议",
            meeting_at=datetime(2026, 8, 3, 10),
            raw_text="行动建议",
            status="ready",
            source_kind="pasted_text",
            created_by=1,
        )
        db.add(meeting)
        db.add(MeetingSynthesis(
            meeting_id=40,
            summary="方法论摘要",
            methodology=[{"title": "先串后写", "rule": "先对齐结构"}, {"title": "标题一致", "rule": "钩子撑起标题"}],
            checklist=[{"item": "先对齐钩子"}],
            decisions=[{"decision": "功能顺序前置"}],
            disagreements=[{"topic": "结尾写法"}],
            open_questions=[{"question": "如何提高互动"}],
            follow_ups=[{"content": "收集样本"}],
        ))
        await db.commit()

        response = await meeting_stats(None, None, db, employee)
        data = response["data"]
        assert data["total_meetings"] == 1
        assert data["total_methodology"] == 2
        assert data["total_checklist"] == 1
        assert data["total_decisions"] == 1
        assert data["total_disagreements"] == 1
        assert data["total_open_questions"] == 1
        assert data["total_follow_ups"] == 1
        assert data["by_week"]
        assert data["by_meeting"][0]["meeting_id"] == 40


@pytest.mark.asyncio
async def test_meeting_summary_groups_detailed_categories(meeting_db):
    async with meeting_db() as db:
        employee = _user(1, "employee")
        meeting = Meeting(
            id=41,
            title="写作复盘",
            meeting_at=datetime(2026, 8, 3, 10),
            raw_text="会议原文",
            status="ready",
            source_kind="pasted_text",
            created_by=1,
            synthesis=MeetingSynthesis(
                summary="先对齐，再动笔。",
                methodology=[{
                    "title": "先串后写",
                    "rule": "先把钩子和产品串成完整故事，再开始写。",
                    "rationale": "避免上下文断裂。",
                    "example": "用真实案例自然过渡到产品功能。",
                    "evidence": "会议复盘指出原版本过渡牵强。",
                }],
                checklist=[{
                    "item": "结尾是否有互动点",
                    "description": "确认读者可以参与讨论。",
                    "when_to_use": "每篇文章动笔前",
                }],
            ),
        )
        db.add_all([employee, meeting])
        await db.commit()

        response = await meeting_summary(None, None, db, employee)
        data = response["data"]
        assert data["total_items"] == 2
        categories = {item["key"]: item for item in data["categories"]}
        assert categories["workflow"]["items"][0]["rationale"] == "避免上下文断裂。"
        assert categories["workflow"]["items"][0]["source_count"] == 1
        assert categories["workflow"]["items"][0]["sources"][0]["meeting_title"] == "写作复盘"
        assert categories["engagement"]["items"][0]["type"] == "checklist"


@pytest.mark.asyncio
async def test_manual_synthesis_update_marks_revision(meeting_db):
    async with meeting_db() as db:
        employee = _user(1, "employee")
        meeting = Meeting(
            id=50,
            title="方法论修订",
            meeting_at=datetime(2026, 8, 11, 10),
            raw_text="先对齐再写。",
            status="ready",
            source_kind="pasted_text",
            created_by=1,
        )
        db.add_all([employee, meeting])
        await db.commit()

        response = await update_meeting_synthesis(
            50,
            MeetingSynthesisUpdate(
                summary="人工确认的摘要",
                methodology=[{"title": "先串后写", "rule": "先把钩子和产品串起来"}],
                checklist=[{"item": "标题是否撑得起钩子"}],
            ),
            db,
            employee,
        )
        assert response["data"]["is_manually_edited"] is True
        assert response["data"]["methodology"][0]["title"] == "先串后写"


@pytest.mark.asyncio
async def test_deleting_meeting_cascades_synthesis_and_suggestions(meeting_db):
    async with meeting_db() as db:
        employee = _user(1, "employee")
        meeting = Meeting(
            id=60,
            title="级联删除",
            meeting_at=datetime(2026, 8, 11, 10),
            raw_text="会议原文",
            status="ready",
            source_kind="pasted_text",
            created_by=1,
            synthesis=MeetingSynthesis(
                summary="摘要",
                methodology=[{"title": "规则", "rule": "保留"}],
            ),
            suggestions=[MeetingSuggestion(
                content="兼容行动项",
                category="其他",
                priority="P1",
                status="proposed",
            )],
        )
        cluster = MeetingMethodologyCluster(
            section="methodology",
            category="workflow",
            title="先串后写",
            rule="先把路线跑通",
            normalized_text="规则：先把路线跑通",
            canonical_fingerprint="cluster-fingerprint",
            source_count=1,
        )
        source = MeetingMethodologySource(
            meeting_id=60,
            section="methodology",
            source_fingerprint="source-fingerprint",
            item={"title": "先串后写", "rule": "先把路线跑通"},
            is_primary=True,
        )
        cluster.sources.append(source)
        meeting.methodology_sources.append(source)
        db.add_all([employee, meeting])
        db.add(cluster)
        await db.commit()
        await db.delete(meeting)
        await db.commit()

        await prune_orphan_methodology_clusters(db)
        await db.commit()

        assert (await db.execute(select(MeetingSynthesis).where(MeetingSynthesis.meeting_id == 60))).scalars().all() == []
        assert (await db.execute(select(MeetingSuggestion).where(MeetingSuggestion.meeting_id == 60))).scalars().all() == []
        assert (await db.execute(select(MeetingMethodologySource).where(MeetingMethodologySource.meeting_id == 60))).scalars().all() == []
        assert (await db.execute(select(MeetingMethodologyCluster).where(MeetingMethodologyCluster.id == cluster.id))).scalars().all() == []

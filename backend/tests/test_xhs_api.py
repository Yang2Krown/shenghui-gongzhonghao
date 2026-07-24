from app.api.v1 import api_router
from app.api.deps import get_current_super_admin_user
from app.api.v1.xhs import note_payload, topic_boards
from app.models.xhs import XhsDailyQuota, XhsEngagementSnapshot, XhsKeyword, XhsKeywordRun, XhsNote, XhsNoteDiscovery, XhsProviderCall, XhsSemanticTopic, XhsTopicMember, XhsTopicSnapshot
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.v1 import xhs as xhs_module
from app.core.admin_permissions import require_admin_permission
from app.db.base import Base
from app.models.user import User
from app.services import xhs_topic_highlights as hl_module
from app.services.llm import deepseek_client as deepseek_module
from app.services.llm.llm_client import ChatResult
from app.services.xhs_topic_highlights import attach_highlights
from app.tasks.xhs_tasks import purge_xhs_media_cache_files


def test_media_proxy_route_registered():
    routes={(route.path,method) for route in api_router.routes for method in getattr(route,"methods",set())}
    assert ("/xhs/media/{note_id}/{kind}","GET") in routes


def test_media_cache_key_stable_and_url_sensitive(tmp_path,monkeypatch):
    monkeypatch.setattr(xhs_module,"MEDIA_CACHE_DIR",tmp_path)
    a1=xhs_module.media_cache_base(1,"cover","https://cdn.example/a.webp")
    a2=xhs_module.media_cache_base(1,"cover","https://cdn.example/a.webp")
    other_url=xhs_module.media_cache_base(1,"cover","https://cdn.example/b.webp")
    other_kind=xhs_module.media_cache_base(1,"avatar","https://cdn.example/a.webp")
    assert a1==a2 and a1!=other_url and a1!=other_kind
    stored=a1.with_suffix(".webp");stored.write_bytes(b"x")
    assert xhs_module.media_cache_lookup(1,"cover","https://cdn.example/a.webp")==stored
    assert xhs_module.media_cache_lookup_exact(1,"cover","https://cdn.example/b.webp") is None
    assert xhs_module.media_cache_lookup(1,"cover","https://cdn.example/b.webp")==stored


def test_media_cache_cleanup_keeps_only_displayable_note_ids(tmp_path):
    keep=(tmp_path/"7_cover_keep.webp");keep.write_bytes(b"keep")
    stale=(tmp_path/"8_cover_stale.webp");stale.write_bytes(b"stale")
    unrelated=(tmp_path/"README.txt");unrelated.write_bytes(b"untouched")
    result=purge_xhs_media_cache_files(tmp_path,{7})
    assert keep.exists() and unrelated.exists() and not stale.exists()
    assert result=={"deleted_files":1,"deleted_bytes":5}


class _FakeResponse:
    def __init__(self,status_code=200,content_type="image/webp",content=b"webp-bytes"):
        self.status_code=status_code;self.headers={"content-type":content_type};self.content=content


class _FakeClient:
    response=_FakeResponse()
    def __init__(self,**kwargs):pass
    async def __aenter__(self):return self
    async def __aexit__(self,*args):return False
    async def get(self,url):return self.response


async def test_fetch_media_to_cache_success(tmp_path,monkeypatch):
    monkeypatch.setattr(xhs_module,"MEDIA_CACHE_DIR",tmp_path)
    monkeypatch.setattr(xhs_module.httpx,"AsyncClient",_FakeClient)
    base=xhs_module.media_cache_base(1,"cover","https://cdn.example/a.webp")
    target=await xhs_module.fetch_media_to_cache("https://cdn.example/a.webp",base)
    assert target.suffix==".webp" and target.read_bytes()==b"webp-bytes"
    assert xhs_module.media_cache_lookup(1,"cover","https://cdn.example/a.webp")==target


async def test_fetch_media_to_cache_rejects_bad_upstream(tmp_path,monkeypatch):
    monkeypatch.setattr(xhs_module,"MEDIA_CACHE_DIR",tmp_path)
    monkeypatch.setattr(xhs_module.httpx,"AsyncClient",_FakeClient)
    _FakeClient.response=_FakeResponse(status_code=403,content_type="text/plain",content=b"")
    with pytest.raises(HTTPException) as exc:
        await xhs_module.fetch_media_to_cache("https://cdn.example/b.webp",tmp_path/"k1")
    assert exc.value.status_code==502
    _FakeClient.response=_FakeResponse(status_code=200,content_type="text/html",content=b"<html>")
    with pytest.raises(HTTPException) as exc:
        await xhs_module.fetch_media_to_cache("https://cdn.example/c.webp",tmp_path/"k2")
    assert exc.value.status_code==502
    assert not (tmp_path/"k1").exists() and not (tmp_path/"k2").exists()


def test_xhs_public_and_admin_routes_are_registered():
    routes={(route.path,method) for route in api_router.routes for method in getattr(route,"methods",set())}
    assert ("/xhs/notes","GET") in routes
    assert ("/xhs/notes/{note_id}","GET") in routes
    assert ("/xhs/topic-boards","GET") in routes
    assert ("/xhs/notes/{note_id}/image-failures","POST") in routes
    assert ("/admin/xhs-monitoring","GET") in routes
    assert ("/admin/xhs-monitoring/keywords/{keyword_id}","PATCH") in routes
    assert ("/admin/xhs-monitoring/keywords/{keyword_id}","DELETE") in routes
    assert ("/admin/xhs-monitoring/image-failures","GET") in routes
    assert ("/admin/xhs-monitoring/image-failures/{report_id}/resolve","POST") in routes
    assert ("/admin/xhs-monitoring/runs/{run_id}/notes","GET") in routes
    assert ("/admin/xhs-monitoring/keywords/{keyword_id}/retry-paid","POST") in routes
    assert ("/admin/xhs-monitoring/notes/{note_id}/refresh-image-free","POST") in routes
    assert ("/admin/xhs-monitoring/cli-auth/sessions","POST") in routes
    assert ("/admin/xhs-monitoring/cli-auth/sessions/{session_id}","GET") in routes
    assert ("/admin/xhs-monitoring/cli-auth/sessions/{session_id}","DELETE") in routes
    assert ("/admin/xhs-monitoring/tikhub-quota","POST") in routes


def test_public_payload_contains_remote_urls_and_no_oss_fields():
    now=datetime(2026,7,16,12,0,0)
    note=XhsNote(note_id="abc",title="标题",content="正文",cover_url="https://sns-webpic.xhscdn.com/a.jpg",avatar_url="https://sns-avatar-qc.xhscdn.com/a.jpg",stable_url="https://www.xiaohongshu.com/explore/abc",first_discovered_at=now,last_discovered_at=now,quality_status="ready",source_payload={})
    payload=note_payload(note,["Codex"],["cli","tikhub"])
    assert payload["cover_url"].startswith("https://")
    assert payload["author"]["avatar_url"].startswith("https://")
    assert not any("oss" in key.lower() or "object_key" in key.lower() for key in payload)
    assert payload["note_id"]=="abc" and payload["providers"]==["cli","tikhub"]


def test_public_payload_prefers_tokenized_search_url():
    now=datetime(2026,7,16,12,0,0)
    tokenized="https://www.xiaohongshu.com/explore/abc?xsec_token=search-token%3D&xsec_source=pc_search"
    note=XhsNote(note_id="abc",stable_url="https://www.xiaohongshu.com/explore/abc",latest_xsec_url=tokenized,first_discovered_at=now,last_discovered_at=now,quality_status="ready",source_payload={})
    assert note_payload(note)["original_url"]==tokenized



async def test_topic_boards_split_filter_and_shape(monkeypatch):
    now=datetime(2026,7,17,12,0,0);ref=datetime(2026,7,16,8,0,0)  # utcnow 已是 07-17，最近采集停留在 07-16
    monkeypatch.setattr(xhs_module,"utcnow",lambda:now)
    async def _no_llm(boards,note_map=None):  # 结构测试不调真实 LLM
        for b in boards:b["ai_highlight"]=None
    monkeypatch.setattr(xhs_module,"attach_highlights",_no_llm)
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for table in ("xhs_keywords","xhs_keyword_runs","xhs_notes","xhs_note_discoveries"):await conn.run_sync(Base.metadata.tables[table].create)
    def note(note_id,likes,published_days,first,last,status="ready",xsec=None):
        return XhsNote(note_id=note_id,title=f"标题{note_id}",note_type="image",author_nickname=f"作者{note_id}",stable_url=f"https://www.xiaohongshu.com/explore/{note_id}",latest_xsec_url=xsec,like_count=likes,published_at=now-timedelta(days=published_days),first_discovered_at=first,last_discovered_at=last,quality_status=status)
    rows=[  # (笔记, 命中的采集关键词)
        (note("f1",6000,1,ref,ref),["大模型","AI"]),
        (note("f2",3000,2,ref,ref),["大模型"]),
        (note("s1",4000,1,ref+timedelta(hours=12),ref+timedelta(hours=12)),["AI"]),
        (note("g1",9000,5,now-timedelta(days=3),ref,xsec="https://www.xiaohongshu.com/explore/g1?xsec_token=test-token&xsec_source=pc_search"),["AI coding"]),
        (note("g2",8000,6,now-timedelta(days=3),ref),["AI coding"]),
        (note("g3",7000,1,now-timedelta(days=2),ref),["AI coding"]),
        (note("g4",6000,2,now-timedelta(days=2),ref),["AI coding"]),
        (note("g5",5000,3,now-timedelta(days=2),ref),["AI coding"]),
        (note("solo",9000,1,ref,ref),["Claude"]),
        (note("old1",9000,4,now-timedelta(days=5),now-timedelta(days=1,hours=13)),["AI工作流"]),
        (note("old2",8000,4,now-timedelta(days=5),now-timedelta(days=1,hours=14)),["AI工作流"]),
        (note("low",200,1,ref,ref),["ghost"]),
        (note("ancient",9000,8,ref,ref),["ghost"]),
        (note("pending",9000,1,ref,ref,status="pending"),["ghost"]),
    ]
    async with AsyncSession(engine) as db:
        keywords={name:XhsKeyword(keyword=name,normalized_keyword=name.lower()) for _,names in rows for name in names}
        db.add_all(keywords.values());await db.flush()
        runs={name:XhsKeywordRun(keyword_id=k.id,run_date=now.date()) for name,k in keywords.items()}
        db.add_all(runs.values());await db.flush()
        for n,names in rows:
            db.add(n);await db.flush()
            for name in names:db.add(XhsNoteDiscovery(note_id=n.id,keyword_id=keywords[name].id,run_id=runs[name].id,provider="cli",discovered_at=n.first_discovered_at))
        await db.commit()
        result=await topic_boards(db=db)
    fresh={b["topic"]:b for b in result["fresh"]};fermenting={b["topic"]:b for b in result["fermenting"]}
    assert result["edition_date"]=="2026-07-16"
    assert result["legacy_fallback"] is True
    assert {"AI","AI coding","大模型"}<=set(fresh) and "AI coding" in fermenting
    assert result["monitor"]["today_new_notes"]==11
    assert result["today_new_notes"]==11


async def test_topic_boards_requires_monitoring_read():
    dependency=require_admin_permission("monitoring:read")
    support=User(id=2,username="support",role="support",is_superuser=False,is_active=True)
    with pytest.raises(HTTPException) as exc:await dependency(support)
    assert exc.value.status_code==403


_XHS_MONITOR_TABLES=("xhs_keywords","xhs_keyword_runs","xhs_notes","xhs_note_discoveries","xhs_daily_quotas","xhs_provider_calls","xhs_image_failure_reports")


async def _async_none():return None
async def _async_zero():return 0


async def test_tikhub_quota_update_super_admin_only_and_persists(monkeypatch):
    from app.core.config import settings as _settings
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.tables["xhs_daily_quotas"].create)
        await conn.run_sync(Base.metadata.tables["admin_audit_logs"].create)
    root=User(id=1,username="root",phone=_settings.SUPER_ADMIN_PHONE,role="admin",is_superuser=True,is_active=True)
    async with AsyncSession(engine) as db:
        result=await xhs_module.update_tikhub_quota(xhs_module.QuotaUpdateBody(limit_count=200),admin=root,db=db)
        assert result["quota"]["limit"]==200 and result["quota"]["remaining"]==200
        quota=(await db.execute(select(XhsDailyQuota))).scalar_one()
        assert quota.limit_count==200
    # 非最高管理员被 deps 闸拦截
    not_root=User(id=2,username="admin2",phone="13900000000",role="admin",is_superuser=True,is_active=True)
    with pytest.raises(HTTPException) as exc:await get_current_super_admin_user(not_root)
    assert exc.value.status_code==403


async def test_monitoring_returns_tikhub_cost_block(monkeypatch):
    from importlib.metadata import PackageNotFoundError
    now=datetime(2026,7,24,10,0,0)
    monkeypatch.setattr(xhs_module,"utcnow",lambda:now)
    monkeypatch.setattr(xhs_module,"cli_auth_error",lambda:_async_none())
    monkeypatch.setattr(xhs_module,"cli_cooldown_remaining",lambda:_async_zero())
    monkeypatch.setattr(xhs_module,"version",lambda _name:(_ for _ in ()).throw(PackageNotFoundError()))
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for table in _XHS_MONITOR_TABLES:await conn.run_sync(Base.metadata.tables[table].create)
    async with AsyncSession(engine) as db:
        db.add(XhsDailyQuota(quota_date=now.date(),limit_count=100,used_count=30,reserved_search_count=5))
        db.add_all([
            XhsProviderCall(provider="tikhub",operation="search",status="success",is_paid=True,request_count=1,estimated_cost=0.07,created_at=now),
            XhsProviderCall(provider="tikhub",operation="detail",status="success",is_paid=True,request_count=1,estimated_cost=0.07,created_at=now),
            XhsProviderCall(provider="tikhub",operation="detail",status="success",is_paid=True,request_count=1,estimated_cost=0.07,created_at=now-timedelta(days=1)),
            XhsProviderCall(provider="cli",operation="search",status="success",is_paid=False,request_count=0,estimated_cost=0,created_at=now),
        ])
        await db.commit()
        result=await xhs_module.monitoring(_admin=None,db=db)
    tikhub=result["tikhub"]
    assert tikhub["today"]["used"]==30 and tikhub["today"]["limit"]==100 and tikhub["today"]["remaining"]==70
    assert tikhub["totals"]["total_calls"]==3 and abs(tikhub["totals"]["total_cost"]-0.21)<1e-6
    by_op={x["operation"]:x for x in tikhub["by_operation"]}
    assert by_op["search"]["count"]==1 and by_op["detail"]["count"]==1  # 今日仅 2 次 success
    assert len(tikhub["daily_cost_7d"])==7 and tikhub["token_configured"] is True


class _FakeRedis:
    store={}
    async def get(self,key):return self.store.get(key)
    async def set(self,key,value,ex=None):self.store[key]=value
    async def aclose(self):pass


class _FakeDeepSeek:
    calls=[];text='"这个话题正处上升期，可从工具横评切入。"\n多余解释'
    async def chat(self,messages,**kwargs):
        type(self).calls.append((messages,kwargs));return ChatResult(text=type(self).text)


class _BoomDeepSeek:
    def __init__(self):raise RuntimeError("DEEPSEEK_API_KEY 未配置")


async def test_attach_highlights_llm_success_and_cache(monkeypatch):
    _FakeRedis.store={};_FakeDeepSeek.calls=[];_FakeDeepSeek.text='"这个话题正处上升期，可从工具横评切入。"\n多余解释'
    monkeypatch.setattr(hl_module.aioredis,"from_url",lambda *a,**kw:_FakeRedis())
    monkeypatch.setattr(deepseek_module,"DeepSeekClient",_FakeDeepSeek)
    note=SimpleNamespace(title="AI编程神器实测",like_count=9000,content="正文内容"*80)
    board={"topic":"AI coding","sample_count":5,"max_likes":9000,"notes":[{"note_id":"g1","likes":9000},{"note_id":"g2","likes":8000}]}
    await attach_highlights([board],{"AI coding":[note]})
    assert board["ai_highlight"]=="这个话题正处上升期，可从工具横评切入。"  # 取第一行并去引号
    messages,kwargs=_FakeDeepSeek.calls[0]
    assert messages[0].role=="system" and "AI coding" in messages[1].content and "AI编程神器实测" in messages[1].content
    assert kwargs["temperature"]==0.5 and kwargs["max_tokens"]==120
    again={"topic":"AI coding","sample_count":5,"max_likes":9000,"notes":[{"note_id":"g1","likes":9000},{"note_id":"g2","likes":8000}]}
    await attach_highlights([again])  # 指纹相同 → 命中缓存
    assert again["ai_highlight"]==board["ai_highlight"] and len(_FakeDeepSeek.calls)==1
    changed={"topic":"AI coding","sample_count":5,"max_likes":9000,"notes":[{"note_id":"g1","likes":9100},{"note_id":"g2","likes":8000}]}
    await attach_highlights([changed])  # 点赞数变了 → 指纹变化 → 重新生成
    assert len(_FakeDeepSeek.calls)==2


async def test_attach_highlights_llm_failure_degrades_to_none(monkeypatch):
    _FakeRedis.store={}
    monkeypatch.setattr(hl_module.aioredis,"from_url",lambda *a,**kw:_FakeRedis())
    monkeypatch.setattr(deepseek_module,"DeepSeekClient",_BoomDeepSeek)
    board={"topic":"AI","sample_count":2,"max_likes":3000,"notes":[{"note_id":"a","likes":3000}]}
    await attach_highlights([board])
    assert board["ai_highlight"] is None and not _FakeRedis.store  # 失败降级为 None 且不写缓存


async def test_attach_highlights_survives_redis_failure(monkeypatch):
    _FakeDeepSeek.calls=[]
    def _broken(*a,**kw):raise ConnectionError("redis down")
    monkeypatch.setattr(hl_module.aioredis,"from_url",_broken)
    monkeypatch.setattr(deepseek_module,"DeepSeekClient",_FakeDeepSeek)
    board={"topic":"x","sample_count":2,"max_likes":1,"notes":[]}
    await attach_highlights([board])
    assert board["ai_highlight"] is not None  # 缓存故障不影响生成


async def _seed_board_db(db,now):
    kw=XhsKeyword(keyword="AI coding",normalized_keyword="ai coding");db.add(kw);await db.flush()
    run=XhsKeywordRun(keyword_id=kw.id,run_date=now.date());db.add(run);await db.flush()
    for nid,likes,cover in (("c1",9000,"https://cdn.example/c1.jpg"),("c2",8000,None)):
        n=XhsNote(note_id=nid,title=f"标题{nid}",content="正文内容"*80,note_type="image",author_nickname=f"作者{nid}",cover_url=cover,stable_url=f"https://www.xiaohongshu.com/explore/{nid}",like_count=likes,published_at=now-timedelta(days=1),first_discovered_at=now,last_discovered_at=now,quality_status="ready")
        db.add(n);await db.flush()
        db.add(XhsNoteDiscovery(note_id=n.id,keyword_id=kw.id,run_id=run.id,provider="cli",discovered_at=now))
    await db.commit()


async def _board_result(monkeypatch,client):
    now=datetime(2026,7,17,12,0,0)
    monkeypatch.setattr(xhs_module,"utcnow",lambda:now)
    _FakeRedis.store={};_FakeDeepSeek.calls=[]
    monkeypatch.setattr(hl_module.aioredis,"from_url",lambda *a,**kw:_FakeRedis())
    monkeypatch.setattr(deepseek_module,"DeepSeekClient",client)
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for table in ("xhs_keywords","xhs_keyword_runs","xhs_notes","xhs_note_discoveries"):await conn.run_sync(Base.metadata.tables[table].create)
    async with AsyncSession(engine) as db:
        await _seed_board_db(db,now)
        return await topic_boards(db=db)


async def test_topic_boards_does_not_generate_keyword_highlight(monkeypatch):
    _FakeDeepSeek.text="这个话题值得写。"
    result=await _board_result(monkeypatch,_FakeDeepSeek)
    assert result["legacy_fallback"] is True
    assert result["fresh"][0]["ai_highlight"] is None and _FakeDeepSeek.calls==[]


async def test_topic_boards_without_semantic_schema_still_returns(monkeypatch):
    result=await _board_result(monkeypatch,_BoomDeepSeek)  # LLM 未配置/抛错 → 接口正常返回，亮点为 None
    assert result["legacy_fallback"] is True and len(result["fresh"])==1
    assert result["fresh"][0]["ai_highlight"] is None


async def test_topic_boards_empty_semantic_table_falls_back_without_llm(monkeypatch):
    now=datetime(2026,7,17,12,0,0);monkeypatch.setattr(xhs_module,"utcnow",lambda:now)
    _FakeDeepSeek.calls=[];monkeypatch.setattr(deepseek_module,"DeepSeekClient",_FakeDeepSeek)
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for table in ("xhs_keywords","xhs_keyword_runs","xhs_notes","xhs_note_discoveries","xhs_semantic_topics"):await conn.run_sync(Base.metadata.tables[table].create)
    async with AsyncSession(engine) as db:
        await _seed_board_db(db,now)
        result=await topic_boards(db=db)
    assert result["legacy_fallback"] is True and len(result["hot"])==1
    assert result["monitor"]["topic_count"]==1 and _FakeDeepSeek.calls==[]


async def test_topic_boards_semantic_payload_has_monitor_and_snapshot_score(monkeypatch):
    now=datetime(2026,7,22,9,0,0);edition=datetime(2026,7,21,8,0,0)
    monkeypatch.setattr(xhs_module,"utcnow",lambda:now)
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    tables=("xhs_notes","xhs_engagement_snapshots","xhs_semantic_topics","xhs_topic_members","xhs_topic_snapshots")
    async with engine.begin() as conn:
        for table in tables:await conn.run_sync(Base.metadata.tables[table].create)
    async with AsyncSession(engine) as db:
        topic=XhsSemanticTopic(public_id="topic-1",name="Agent 工具更新",summary="从工具升级切入",centroid=[1.0,0.0],first_seen_at=edition-timedelta(days=2),last_seen_at=edition,active_days=3)
        db.add(topic);await db.flush()
        notes=[]
        for index,likes in enumerate((3200,2800),1):
            note=XhsNote(note_id=f"s{index}",title=f"语义笔记{index}",note_type="image",author_nickname=f"作者{index}",stable_url=f"https://www.xiaohongshu.com/explore/s{index}",like_count=likes,published_at=edition+timedelta(hours=22),first_discovered_at=edition,last_discovered_at=edition,quality_status="ready")
            db.add(note);await db.flush();notes.append(note)
            db.add(XhsTopicMember(topic_id=topic.id,note_id=note.id,similarity=.9,assigned_at=edition))
            db.add(XhsEngagementSnapshot(note_id=note.id,snapshot_date=edition.date(),like_count=likes,collect_count=10,comment_count=5,share_count=1))
        db.add(XhsTopicSnapshot(topic_id=topic.id,snapshot_date=edition.date(),wave="morning",snapshot_at=edition,note_count=2,author_count=2,new_notes_24h=2,new_authors_24h=2,engagement_total=6032,engagement_growth=12.5,fermentation_score=76.0,evidence=["今日再次监测到 2 篇"]))
        await db.commit()
        result=await topic_boards(db=db)
    assert result["edition_date"]=="2026-07-21"
    assert result["hot"][0]["fermentation_score"]==76.0
    assert result["hot"][0]["trend_points"][0]["score"]==6032
    assert result["monitor"]=={"topic_count":1,"sample_count":2,"fresh_count":1,"max_likes":3200,"today_new_notes":2}


async def test_topic_boards_fermenting_prefers_sustained_over_sudden_spike(monkeypatch):
    """持续发酵应以"一直在热"为主导：多日反复在热的老话题排在今日突发新话题前面。"""
    now=datetime(2026,7,22,9,0,0);edition=datetime(2026,7,21,8,0,0)
    monkeypatch.setattr(xhs_module,"utcnow",lambda:now)
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    tables=("xhs_notes","xhs_engagement_snapshots","xhs_semantic_topics","xhs_topic_members","xhs_topic_snapshots")
    async with engine.begin() as conn:
        for table in tables:await conn.run_sync(Base.metadata.tables[table].create)
    async with AsyncSession(engine) as db:
        # sustained：连续 6 个采集日在热、互动持续上涨，但今日仅 2 篇新笔记
        sustained=XhsSemanticTopic(public_id="topic-sustained",name="持续发酵老话题",summary="s",centroid=[1.0,0.0],first_seen_at=edition-timedelta(days=6),last_seen_at=edition,active_days=6)
        # spike：昨日才出现、今日突然 9 篇新笔记但仅 2 个采集日
        spike=XhsSemanticTopic(public_id="topic-spike",name="今日突发新话题",summary="s",centroid=[0.0,1.0],first_seen_at=edition-timedelta(days=1),last_seen_at=edition,active_days=2)
        db.add_all([sustained,spike]);await db.flush()
        async def _seed(topic,count,likes):
            for index in range(count):
                note=XhsNote(note_id=f"{topic.public_id}-{index}",title=f"笔记{topic.public_id}{index}",note_type="image",author_nickname=f"作者{topic.public_id}{index}",stable_url=f"https://www.xiaohongshu.com/explore/{topic.public_id}{index}",like_count=likes,published_at=edition-timedelta(hours=2),first_discovered_at=edition,last_discovered_at=edition,quality_status="ready")
                db.add(note);await db.flush()
                db.add(XhsTopicMember(topic_id=topic.id,note_id=note.id,similarity=.9,assigned_at=edition))
        await _seed(sustained,2,3200);await _seed(spike,9,8000)
        db.add(XhsTopicSnapshot(topic_id=sustained.id,snapshot_date=edition.date(),wave="morning",snapshot_at=edition,note_count=2,author_count=2,new_notes_24h=2,new_authors_24h=2,engagement_total=9000,engagement_growth=40.0,fermentation_score=70.0,evidence=[]))
        db.add(XhsTopicSnapshot(topic_id=spike.id,snapshot_date=edition.date(),wave="morning",snapshot_at=edition,note_count=9,author_count=9,new_notes_24h=9,new_authors_24h=9,engagement_total=72000,engagement_growth=0.0,fermentation_score=55.0,evidence=[]))
        await db.commit()
        result=await topic_boards(db=db)
    fermenting=[b["topic"] for b in result["fermenting"]]
    assert fermenting[0]=="持续发酵老话题" and "今日突发新话题" in fermenting


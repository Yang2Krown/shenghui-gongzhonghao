from app.api.v1 import api_router
from app.api.v1.xhs import note_payload, topic_boards
from app.models.xhs import XhsKeyword, XhsKeywordRun, XhsNote, XhsNoteDiscovery
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.v1 import xhs as xhs_module
from app.core.admin_permissions import require_admin_permission
from app.db.base import Base
from app.models.user import User
from app.services import xhs_topic_highlights as hl_module
from app.services.llm import deepseek_client as deepseek_module
from app.services.llm.llm_client import ChatResult
from app.services.xhs_topic_highlights import attach_highlights


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
    assert xhs_module.media_cache_lookup(1,"cover","https://cdn.example/b.webp") is None


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


def test_public_payload_contains_remote_urls_and_no_oss_fields():
    now=datetime(2026,7,16,12,0,0)
    note=XhsNote(note_id="abc",title="标题",content="正文",cover_url="https://sns-webpic.xhscdn.com/a.jpg",avatar_url="https://sns-avatar-qc.xhscdn.com/a.jpg",stable_url="https://www.xiaohongshu.com/explore/abc",first_discovered_at=now,last_discovered_at=now,quality_status="ready",source_payload={})
    payload=note_payload(note,["Codex"],["cli","tikhub"])
    assert payload["cover_url"].startswith("https://")
    assert payload["author"]["avatar_url"].startswith("https://")
    assert not any("oss" in key.lower() or "object_key" in key.lower() for key in payload)
    assert payload["note_id"]=="abc" and payload["providers"]==["cli","tikhub"]



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
        (note("g1",9000,5,now-timedelta(days=3),ref,xsec="https://xsec.example/g1"),["AI coding"]),
        (note("g2",8000,6,now-timedelta(days=3),ref),["AI coding"]),
        (note("g3",7000,1,now-timedelta(days=2),ref),["AI coding"]),
        (note("g4",6000,2,now-timedelta(days=2),ref),["AI coding"]),
        (note("g5",5000,3,now-timedelta(days=2),ref),["AI coding"]),
        (note("solo",9000,1,ref,ref),["Claude"]),
        (note("old1",9000,4,now-timedelta(days=5),now-timedelta(days=1,hours=13)),["AI工作流"]),
        (note("old2",8000,4,now-timedelta(days=5),now-timedelta(days=1,hours=14)),["AI工作流"]),
        (note("low",2000,1,ref,ref),["ghost"]),
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
    assert result["generated_at"]==now.isoformat()
    assert set(fresh)=={"大模型","AI"}  # 按采集关键词分组，f1 命中两个词分别计入；锚点是最近采集日 07-16 而非 utcnow 当天
    assert set(fermenting)=={"AI coding"}  # 之前已成立且最近采集日仍活跃
    assert "Claude" not in fresh  # sample_count<2 被过滤
    assert "AI工作流" not in fermenting and "ghost" not in fermenting  # 最近采集日无新增/不满足列表硬过滤的不上榜
    assert fresh["大模型"]["sample_count"]==2 and fresh["大模型"]["recent_3d_count"]==2
    assert fresh["大模型"]["first_seen_at"]==ref.isoformat() and fresh["大模型"]["max_likes"]==6000
    board=fermenting["AI coding"]
    assert board["sample_count"]==5 and board["recent_3d_count"]==3 and board["max_likes"]==9000
    assert board["first_seen_at"]==(now-timedelta(days=3)).isoformat() and board["last_seen_at"]==ref.isoformat()
    assert [n["note_id"] for n in board["notes"]]==["g1","g2","g3","g4"]  # 只取点赞前 4 且降序
    assert [n["likes"] for n in board["notes"]]==[9000,8000,7000,6000]
    top=board["notes"][0]
    assert top["author"]=="作者g1" and top["original_url"]=="https://xsec.example/g1" and top["note_type"]=="image"
    assert "cover_url" in top and board["ai_highlight"] is None
    assert board["notes"][1]["original_url"]=="https://www.xiaohongshu.com/explore/g2"


async def test_topic_boards_requires_monitoring_read():
    dependency=require_admin_permission("monitoring:read")
    support=User(id=2,username="support",role="support",is_superuser=False,is_active=True)
    with pytest.raises(HTTPException) as exc:await dependency(support)
    assert exc.value.status_code==403


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
        n=XhsNote(note_id=nid,title=f"标题{nid}",content="正文内容"*80,note_type="image",author_nickname="作者",cover_url=cover,stable_url=f"https://www.xiaohongshu.com/explore/{nid}",like_count=likes,published_at=now-timedelta(days=1),first_discovered_at=now,last_discovered_at=now,quality_status="ready")
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


async def test_topic_boards_ai_highlight_and_cover_url(monkeypatch):
    _FakeDeepSeek.text="这个话题值得写。"
    result=await _board_result(monkeypatch,_FakeDeepSeek)
    board=result["fresh"][0]
    assert board["ai_highlight"]=="这个话题值得写。"
    assert board["notes"][0]["cover_url"]=="https://cdn.example/c1.jpg" and board["notes"][1]["cover_url"] is None
    assert len(_FakeDeepSeek.calls)==1


async def test_topic_boards_ai_highlight_failure_still_returns(monkeypatch):
    result=await _board_result(monkeypatch,_BoomDeepSeek)  # LLM 未配置/抛错 → 接口正常返回，亮点为 None
    board=result["fresh"][0]
    assert board["ai_highlight"] is None and board["notes"][0]["cover_url"]=="https://cdn.example/c1.jpg"

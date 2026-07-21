"""小红书素材 demo（管理员可见）与后台监测接口。"""
import asyncio
from datetime import datetime, timedelta
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import shutil

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import String, and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError

from app.api.deps import get_current_super_admin_user
from app.core.admin_permissions import require_admin_permission
from app.core.config import settings
from app.core.timezone import utcnow
from app.db.session import get_db
from app.models.admin_audit import AdminAuditLog
from app.models.user import User
from app.models.xhs import XhsDailyQuota, XhsEngagementSnapshot, XhsImageFailureReport, XhsKeyword, XhsKeywordRun, XhsNote, XhsNoteDiscovery, XhsProviderCall, XhsSemanticTopic, XhsTopicMember, XhsTopicSnapshot
from app.services.xhs_cli_auth import XhsQrLoginManager
from app.services.xhs_collection import (
    CLI_AUTH_INVALID_KEY, CLI_COOLDOWN_KEY, DAILY_MIN_LIKES_EXCLUSIVE,
    WEEKLY_MIN_LIKES_EXCLUSIVE, _xsec_token, eligibility_clause,
)
from app.services.xhs_topic_highlights import attach_highlights
from app.tasks.xhs_tasks import collect_keyword_task, refresh_note_image_task

router=APIRouter();admin_router=APIRouter()
PUBLIC_STATUSES=("ready","ready_degraded","synced")

# 封面/头像代理：小红书 CDN 对外站 Referer 一律 403，且 URL 有时效，
# 前端直连不可靠；统一由后端代取并落盘缓存（URL 变化 → 缓存键变化）。
# 注意：该接口刻意不做登录鉴权——浏览器 <img> 请求无法携带 JWT。
# 安全上可接受：note_id 是小红书公开 ID，封面/头像本身是公开内容，
# 且只代理库内已收录的笔记（未知 note_id 直接 404，无法诱导代取任地址）。
MEDIA_KINDS=("cover","avatar")
MEDIA_CACHE_DIR=Path(settings.UPLOAD_DIR)/"xhs_media"
MEDIA_MAX_BYTES=20*1024*1024
MEDIA_EXTENSIONS={"image/webp":".webp","image/jpeg":".jpg","image/png":".png","image/gif":".gif"}
qr_login_manager=XhsQrLoginManager(settings.XHS_CLI_COOKIE_FILE)


def cookie_saved_at()->str|None:
    try:
        payload=json.loads(Path(settings.XHS_CLI_COOKIE_FILE).read_text())
        saved_at=float(payload.get("saved_at") or 0)
        return datetime.fromtimestamp(saved_at).isoformat() if saved_at else None
    except (OSError,ValueError,TypeError,json.JSONDecodeError):
        return None


async def cli_auth_error()->str|None:
    redis=aioredis.from_url(settings.CELERY_BROKER_URL,decode_responses=True)
    try:return await redis.get(CLI_AUTH_INVALID_KEY)
    except Exception:return None
    finally:await redis.aclose()


async def cli_cooldown_remaining()->int:
    redis=aioredis.from_url(settings.CELERY_BROKER_URL,decode_responses=True)
    try:return max(0,await redis.ttl(CLI_COOLDOWN_KEY))
    except Exception:return 0
    finally:await redis.aclose()


async def clear_cli_auth_blocks()->None:
    redis=aioredis.from_url(settings.CELERY_BROKER_URL,decode_responses=True)
    try:await redis.delete(CLI_AUTH_INVALID_KEY,CLI_COOLDOWN_KEY)
    finally:await redis.aclose()


def media_cache_base(note_pk:int,kind:str,url:str)->Path:
    digest=hashlib.sha1(url.encode()).hexdigest()[:16]
    return MEDIA_CACHE_DIR/f"{note_pk}_{kind}_{digest}"


def media_cache_lookup_exact(note_pk:int,kind:str,url:str)->Path|None:
    base=media_cache_base(note_pk,kind,url)
    matches=sorted(base.parent.glob(base.name+".*")) if base.parent.is_dir() else []
    return next((item for item in matches if not item.name.endswith(".tmp")),None)


def media_cache_lookup_history(note_pk:int,kind:str)->Path|None:
    if not MEDIA_CACHE_DIR.is_dir():return None
    matches=[item for item in MEDIA_CACHE_DIR.glob(f"{note_pk}_{kind}_*.*") if not item.name.endswith(".tmp")]
    return max(matches,key=lambda item:item.stat().st_mtime) if matches else None


def media_cache_lookup(note_pk:int,kind:str,url:str)->Path|None:
    return media_cache_lookup_exact(note_pk,kind,url) or media_cache_lookup_history(note_pk,kind)


async def fetch_media_to_cache(url:str,base:Path)->Path:
    try:
        async with httpx.AsyncClient(timeout=15,follow_redirects=True) as client:
            resp=await client.get(url)  # 不带 Referer，绕过 CDN 防盗链
    except httpx.HTTPError as exc:
        raise HTTPException(502,f"上游图片请求失败（{type(exc).__name__}）")
    if resp.status_code!=200:raise HTTPException(502,f"上游图片请求失败（HTTP {resp.status_code}）")
    content_type=resp.headers.get("content-type","").split(";")[0].strip().lower()
    ext=MEDIA_EXTENSIONS.get(content_type)
    if not ext:raise HTTPException(502,f"上游返回了非图片内容（{content_type or '未知类型'}）")
    data=resp.content
    if not data or len(data)>MEDIA_MAX_BYTES:raise HTTPException(502,"上游图片内容为空或超过大小限制")
    base.parent.mkdir(parents=True,exist_ok=True)
    target=base.with_suffix(ext);tmp=base.with_suffix(ext+".tmp")
    tmp.write_bytes(data);tmp.replace(target)
    return target


def original_note_url(note:XhsNote)->str:
    """只有真正携带 xsec_token 的搜索链接才作为直达链接返回。"""
    return note.latest_xsec_url if _xsec_token(note.latest_xsec_url) else note.stable_url


def note_payload(note:XhsNote, keywords:list[str]|None=None, providers:list[str]|None=None)->dict:
    return {"note_id":note.note_id,"title":note.title,"content":note.content,"published_at":note.published_at.isoformat() if note.published_at else None,"note_type":note.note_type,"author":{"id":note.author_id,"nickname":note.author_nickname,"bio":note.author_bio,"avatar_url":note.avatar_url},"cover_url":note.cover_url,"native_tags":note.native_tags or [],"ai_summary":note.ai_summary,"ai_topics":note.ai_topics or [],"engagement":{"likes":note.like_count,"collects":note.collect_count,"comments":note.comment_count,"shares":note.share_count,"views":note.view_count},"stable_url":note.stable_url,"original_url":original_note_url(note),"first_discovered_at":note.first_discovered_at.isoformat(),"last_discovered_at":note.last_discovered_at.isoformat(),"status":note.quality_status,"comprehensive_score":note.comprehensive_score,"keywords":keywords or [],"providers":providers or []}


async def note_context(db:AsyncSession,note_ids:list[int])->dict[int,dict]:
    if not note_ids:return {}
    rows=(await db.execute(select(XhsNoteDiscovery.note_id,XhsKeyword.keyword,XhsNoteDiscovery.provider).join(XhsKeyword,XhsKeyword.id==XhsNoteDiscovery.keyword_id).where(XhsNoteDiscovery.note_id.in_(note_ids)))).all();out={}
    for nid,keyword,provider in rows:
        item=out.setdefault(nid,{"keywords":[],"providers":[]})
        if keyword not in item["keywords"]:item["keywords"].append(keyword)
        if provider not in item["providers"]:item["providers"].append(provider)
    return out


@router.get("/notes")
async def list_notes(q:str|None=None,keyword:str|None=None,topic:str|None=None,semantic_topic_id:str|None=None,note_type:str="all",range:str=Query("7d",pattern="^(1d|3d|7d)$"),sort:str=Query("comprehensive",pattern="^(comprehensive|latest|likes|collects|comments)$"),page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),_admin:User=Depends(require_admin_permission("monitoring:read")),db:AsyncSession=Depends(get_db)):
    days={"1d":1,"3d":3,"7d":7}[range];now=utcnow();cutoff=now-timedelta(days=days)
    day_cutoff=now-timedelta(hours=24)
    range_eligibility=and_(
        XhsNote.published_at>=cutoff,
        or_(
            and_(XhsNote.published_at>=day_cutoff,XhsNote.like_count>DAILY_MIN_LIKES_EXCLUSIVE),
            and_(XhsNote.published_at<day_cutoff,XhsNote.like_count>WEEKLY_MIN_LIKES_EXCLUSIVE),
        ),
    )
    stmt=select(XhsNote).where(range_eligibility,XhsNote.quality_status.in_(PUBLIC_STATUSES))
    if q:
        like=f"%{q.strip()}%";stmt=stmt.where(or_(XhsNote.title.ilike(like),XhsNote.content.ilike(like),XhsNote.author_nickname.ilike(like),XhsNote.note_id.ilike(like)))
    if note_type!="all":stmt=stmt.where(XhsNote.note_type==note_type)
    if topic:stmt=stmt.where(func.cast(XhsNote.ai_topics,String).ilike(f"%{topic}%"))
    if semantic_topic_id:
        stmt=stmt.where(select(XhsTopicMember.id).join(XhsSemanticTopic,XhsSemanticTopic.id==XhsTopicMember.topic_id).where(XhsTopicMember.note_id==XhsNote.id,XhsSemanticTopic.public_id==semantic_topic_id).exists())
    if keyword:
        normalized=" ".join(keyword.lower().split())
        stmt=stmt.where(select(XhsNoteDiscovery.id).join(XhsKeyword,XhsKeyword.id==XhsNoteDiscovery.keyword_id).where(XhsNoteDiscovery.note_id==XhsNote.id,XhsKeyword.normalized_keyword==normalized).exists())
    order={"comprehensive":XhsNote.comprehensive_score,"latest":XhsNote.published_at,"likes":XhsNote.like_count,"collects":XhsNote.collect_count,"comments":XhsNote.comment_count}[sort]
    count_stmt=select(func.count()).select_from(stmt.order_by(None).subquery());total=(await db.scalar(count_stmt)) or 0
    notes=(await db.scalars(stmt.order_by(desc(order).nullslast()).offset((page-1)*page_size).limit(page_size))).all();ctx=await note_context(db,[n.id for n in notes])
    return {"items":[note_payload(n,**ctx.get(n.id,{})) for n in notes],"page":page,"page_size":page_size,"total":total,"hard_filters":{"range":range,"max_age_days":days,"likes_gt":DAILY_MIN_LIKES_EXCLUSIVE if range=="1d" else None,"levels":{"daily":{"max_age_hours":24,"likes_gt":DAILY_MIN_LIKES_EXCLUSIVE},"weekly":{"max_age_days":days,"likes_gt":WEEKLY_MIN_LIKES_EXCLUSIVE}},"types":["image","video"]}}


@router.get("/notes/{note_id}")
async def get_note(note_id:str,_admin:User=Depends(require_admin_permission("monitoring:read")),db:AsyncSession=Depends(get_db)):
    now=utcnow();note=(await db.execute(select(XhsNote).where(XhsNote.note_id==note_id,eligibility_clause(now),XhsNote.quality_status.in_(PUBLIC_STATUSES)))).scalar_one_or_none()
    if not note:raise HTTPException(404,"素材不存在或不符合展示资格")
    ctx=await note_context(db,[note.id]);return note_payload(note,**ctx.get(note.id,{}))


@router.get("/topic-boards")
async def topic_boards(_admin:User=Depends(require_admin_permission("monitoring:read")),db:AsyncSession=Depends(get_db)):
    now=utcnow()
    try: topics=(await db.scalars(select(XhsSemanticTopic).where(XhsSemanticTopic.status=="active").order_by(desc(XhsSemanticTopic.last_seen_at)))).all()
    except OperationalError:
        await db.rollback();return {"generated_at":now.isoformat(),"edition_date":now.date().isoformat(),"hot":[],"fermenting":[],"fresh":[]}
    day_start=now.replace(hour=0,minute=0,second=0,microsecond=0)
    hot=[];fermenting=[]
    for topic in topics:
        notes=(await db.scalars(select(XhsNote).join(XhsTopicMember,XhsTopicMember.note_id==XhsNote.id).where(XhsTopicMember.topic_id==topic.id).order_by(desc(XhsNote.like_count)))).all()
        recent=[n for n in notes if n.last_discovered_at>=day_start]
        authors={n.author_id or n.author_nickname for n in notes if n.author_id or n.author_nickname};recent_authors={n.author_id or n.author_nickname for n in recent if n.author_id or n.author_nickname}
        snapshot=(await db.scalars(select(XhsTopicSnapshot).where(XhsTopicSnapshot.topic_id==topic.id).order_by(desc(XhsTopicSnapshot.snapshot_at)).limit(1))).first()
        note_ids=[n.id for n in notes]
        interactions=(await db.scalars(select(XhsEngagementSnapshot).where(XhsEngagementSnapshot.note_id.in_(note_ids),XhsEngagementSnapshot.snapshot_date>=now.date()-timedelta(days=6)).order_by(XhsEngagementSnapshot.snapshot_date))).all() if note_ids else []
        daily={}
        for item in interactions:
            point=daily.setdefault(item.snapshot_date,{"score":0,"notes":set()})
            point["score"]+=sum(value or 0 for value in (item.like_count,item.collect_count,item.comment_count,item.share_count));point["notes"].add(item.note_id)
        trend_points=[{"at":date.isoformat(),"score":value["score"],"new_notes":len(value["notes"])} for date,value in sorted(daily.items())]
        payload={"topic_id":topic.public_id,"topic":topic.name,"ai_highlight":topic.summary,"sample_count":len(notes),"author_count":len(authors),"new_notes_24h":len(recent),"new_authors_24h":len(recent_authors),"max_likes":max((n.like_count or 0 for n in notes),default=0),"first_seen_at":topic.first_seen_at.isoformat(),"last_seen_at":topic.last_seen_at.isoformat(),"active_days":topic.active_days,"engagement_growth":snapshot.engagement_growth if snapshot else 0,"evidence":snapshot.evidence if snapshot else [],"trend_points":trend_points,"notes":[{"note_id":n.note_id,"title":n.title,"likes":n.like_count,"note_type":n.note_type,"author":n.author_nickname,"cover_url":n.cover_url,"original_url":original_note_url(n)} for n in notes[:4]]}
        if len(recent)>=2 and len(recent_authors)>=2:hot.append(payload)
        if topic.first_seen_at<day_start and topic.active_days>=2 and len(notes)>=2 and len(authors)>=2 and recent:fermenting.append(payload)
    hot.sort(key=lambda item:(item["new_notes_24h"],item["max_likes"]),reverse=True);fermenting.sort(key=lambda item:(item["new_notes_24h"],item["max_likes"]),reverse=True)
    generated=max((s.snapshot_at for s in (await db.scalars(select(XhsTopicSnapshot).order_by(desc(XhsTopicSnapshot.snapshot_at)).limit(1))).all()),default=now)
    return {"generated_at":generated.isoformat(),"edition_date":now.date().isoformat(),"hot":hot[:6],"fermenting":fermenting[:20],"fresh":hot[:6]}


async def _legacy_topic_boards(db:AsyncSession,now:datetime,attach_ai:bool=True)->dict:
    """Deployment-safe fallback while the semantic migration/backfill is being applied."""
    recent_3d=now-timedelta(days=3);notes=(await db.scalars(select(XhsNote).where(eligibility_clause(now),XhsNote.quality_status.in_(PUBLIC_STATUSES)))).all()
    ref=max((n.last_discovered_at for n in notes),default=now).replace(hour=0,minute=0,second=0,microsecond=0);ctx=await note_context(db,[n.id for n in notes]);groups={}
    for note in notes:
        for keyword in ctx.get(note.id,{}).get("keywords",[]): groups.setdefault(keyword,[]).append(note)
    fresh=[];fermenting=[]
    for keyword,items in groups.items():
        if len(items)<2: continue
        first=min(n.first_discovered_at for n in items);last=max(n.last_discovered_at for n in items)
        recent=[n for n in items if n.last_discovered_at>=ref]
        authors={n.author_id or n.author_nickname for n in items if n.author_id or n.author_nickname}
        recent_authors={n.author_id or n.author_nickname for n in recent if n.author_id or n.author_nickname}
        active_days=max(1,min(7,(last.date()-first.date()).days+1))
        score=min(100,round(25+len(items)*6+len(authors)*4+len(recent)*5,1))
        board={"topic_id":None,"keyword":keyword,"topic":keyword,"fallback_source":"keyword","sample_count":len(items),"author_count":len(authors),"new_notes_24h":len(recent),"new_authors_24h":len(recent_authors),"recent_3d_count":sum(n.published_at>=recent_3d for n in items),"max_likes":max(n.like_count for n in items),"first_seen_at":first.isoformat(),"last_seen_at":last.isoformat(),"active_days":active_days,"engagement_growth":0,"fermentation_score":score,"evidence":[f"今日采集再次命中 {len(recent)} 篇",f"共 {len(authors)} 位作者",f"近 7 日共 {len(items)} 篇合格素材"],"trend_points":[{"at":last.isoformat(),"score":score,"new_notes":len(recent)}],"notes":[{"note_id":n.note_id,"title":n.title,"likes":n.like_count,"note_type":n.note_type,"author":n.author_nickname,"cover_url":n.cover_url,"original_url":original_note_url(n)} for n in sorted(items,key=lambda n:n.like_count,reverse=True)[:4]]}
        if len(recent)>=2 and len(recent_authors)>=2:fresh.append(dict(board))
        if first<ref and recent and len(authors)>=2:fermenting.append(dict(board))
    fresh.sort(key=lambda b:b["max_likes"],reverse=True);fermenting.sort(key=lambda b:b["max_likes"],reverse=True)
    if attach_ai:
        try: await attach_highlights(fresh[:5]+fermenting[:5],groups)
        except Exception:
            for board in fresh+fermenting: board.setdefault("ai_highlight",None)
    else:
        for board in fresh+fermenting:board.setdefault("ai_highlight",None)
    return {"generated_at":now.isoformat(),"edition_date":ref.date().isoformat(),"hot":fresh[:5],"fresh":fresh[:5],"fermenting":fermenting[:5],"legacy_fallback":True}


@router.get("/topics/{topic_id}")
async def topic_detail(topic_id:str,_admin:User=Depends(require_admin_permission("monitoring:read")),db:AsyncSession=Depends(get_db)):
    topic=(await db.execute(select(XhsSemanticTopic).where(XhsSemanticTopic.public_id==topic_id))).scalar_one_or_none()
    if not topic: raise HTTPException(404,"语义话题不存在")
    notes=(await db.scalars(select(XhsNote).join(XhsTopicMember,XhsTopicMember.note_id==XhsNote.id).where(XhsTopicMember.topic_id==topic.id).order_by(desc(XhsNote.like_count)))).all();ctx=await note_context(db,[n.id for n in notes])
    trends=(await db.scalars(select(XhsTopicSnapshot).where(XhsTopicSnapshot.topic_id==topic.id).order_by(XhsTopicSnapshot.snapshot_at))).all()
    return {"topic_id":topic.public_id,"topic":topic.name,"summary":topic.summary,"first_seen_at":topic.first_seen_at.isoformat(),"last_seen_at":topic.last_seen_at.isoformat(),"active_days":topic.active_days,"trend_points":[{"at":s.snapshot_at.isoformat(),"score":s.fermentation_score,"new_notes":s.new_notes_24h,"authors":s.author_count} for s in trends],"notes":[note_payload(n,**ctx.get(n.id,{})) for n in notes]}


@router.get("/media/{note_id}/{kind}")
async def note_media(note_id:str,kind:str,db:AsyncSession=Depends(get_db)):
    if kind not in MEDIA_KINDS:raise HTTPException(404,"不支持的图片类型")
    note=(await db.execute(select(XhsNote).where(XhsNote.note_id==note_id))).scalar_one_or_none()
    if not note:raise HTTPException(404,"素材不存在")
    url=note.cover_url if kind=="cover" else note.avatar_url
    if not url:raise HTTPException(404,"该素材没有对应图片")
    cached=media_cache_lookup_exact(note.id,kind,url)
    if cached is None:
        try:cached=await fetch_media_to_cache(url,media_cache_base(note.id,kind,url))
        except HTTPException:
            cached=media_cache_lookup_history(note.id,kind)
            if cached is None:raise
    return FileResponse(cached,headers={"Cache-Control":"public, max-age=86400"})


class ImageFailureBody(BaseModel):
    image_kind:str=Field("cover",pattern="^(cover|avatar)$")
    failed_url:str=Field(...,min_length=8,max_length=2000)


@router.post("/notes/{note_id}/image-failures",status_code=202)
async def report_image_failure(note_id:str,body:ImageFailureBody,admin:User=Depends(require_admin_permission("monitoring:read")),db:AsyncSession=Depends(get_db)):
    note=(await db.execute(select(XhsNote).where(XhsNote.note_id==note_id))).scalar_one_or_none()
    if not note:raise HTTPException(404,"素材不存在")
    row=(await db.execute(select(XhsImageFailureReport).where(XhsImageFailureReport.note_id==note.id,XhsImageFailureReport.image_kind==body.image_kind,XhsImageFailureReport.failed_url==body.failed_url))).scalar_one_or_none()
    if row:row.failure_count+=1;row.last_failed_at=utcnow();row.status="open"
    else:db.add(XhsImageFailureReport(note_id=note.id,image_kind=body.image_kind,failed_url=body.failed_url,reporter_user_id=admin.id,last_failed_at=utcnow()))
    if body.image_kind=="cover":note.media_status="suspected_invalid"
    await db.commit();return {"accepted":True,"paid_request_triggered":False}


def run_payload(r:XhsKeywordRun,k:XhsKeyword)->dict:
    rejections=r.rejection_counts or {}
    levels=rejections.get("_levels") if isinstance(rejections.get("_levels"),dict) else {}
    return {"id":r.id,"keyword_id":k.id,"keyword":k.keyword,"keyword_type":k.keyword_type,"group":k.schedule_group,"status":r.status,"tikhub_status":r.tikhub_status,"cli_status":r.cli_status,"tikhub_raw_count":r.tikhub_raw_count,"cli_raw_count":r.cli_raw_count,"merged_count":r.merged_count,"within_week_count":r.within_week_count,"eligible_like_count":r.eligible_like_count,"level_stats":{"daily":levels.get("daily",{}),"weekly":levels.get("weekly",{})},"searches":rejections.get("_searches",[]),"filtered_count":r.filtered_count,"final_count":r.final_count,"displayable_count":r.displayable_count,"paid_call_count":r.paid_call_count,"rejection_counts":rejections,"has_search_diagnostics":bool(rejections.get("_search_diagnostics")) or r.run_source!="local_agent","search_state":"unrecognized" if rejections.get("_search_state_unrecognized") else "empty" if rejections.get("_search_state_empty") else "ok","detail_attempted_count":rejections.get("_detail_attempted",0),"detail_success_count":rejections.get("_detail_success",0),"run_source":r.run_source,"error_message":r.error_message,"finished_at":r.finished_at.isoformat() if r.finished_at else None}


@admin_router.get("")
async def monitoring(_admin:User=Depends(require_admin_permission("monitoring:read")),db:AsyncSession=Depends(get_db)):
    today=utcnow().date();keywords=(await db.scalars(select(XhsKeyword).order_by(XhsKeyword.keyword_type,XhsKeyword.schedule_group,XhsKeyword.id))).all();run_rows=(await db.execute(select(XhsKeywordRun,XhsKeyword).join(XhsKeyword,XhsKeyword.id==XhsKeywordRun.keyword_id).where(XhsKeywordRun.run_date==today).order_by(XhsKeyword.schedule_group,XhsKeyword.id))).all();runs=[{**run_payload(r,k),"wave":r.wave,"scheduled_for":r.scheduled_for.isoformat() if r.scheduled_for else None} for r,k in run_rows]
    quota=(await db.execute(select(XhsDailyQuota).where(XhsDailyQuota.quota_date==today))).scalar_one_or_none();quota_data={"used":quota.used_count if quota else 0,"limit":quota.limit_count if quota else settings.TIKHUB_DAILY_LIMIT,"reserved_searches":quota.reserved_search_count if quota else 0};quota_data["remaining"]=max(0,quota_data["limit"]-quota_data["used"])
    day_start=utcnow().replace(hour=0,minute=0,second=0,microsecond=0)
    successful_cost=(await db.scalar(select(func.coalesce(func.sum(XhsProviderCall.estimated_cost),0)).where(XhsProviderCall.provider=="tikhub",XhsProviderCall.status=="success",XhsProviderCall.created_at>=day_start))) or 0
    quota_data["estimated_cost_cny"]=round(float(successful_cost),4)
    calls=(await db.scalars(select(XhsProviderCall).where(XhsProviderCall.created_at>=utcnow()-timedelta(days=1)).order_by(desc(XhsProviderCall.id)).limit(100))).all()
    def health(provider):
        rows=[x for x in calls if x.provider==provider and x.status in ("success","failed")];recent=rows[:10];ok=sum(x.status=="success" for x in recent)
        enough=len(recent)>=3;rate=ok/len(recent) if recent else None
        return {"status":"ok" if not enough or rate>=.7 else "warning" if rate>=.4 else "critical","success_rate":round(rate*100,1) if enough else None,"recent_calls":len(recent)}
    funnel={key:sum(getattr(r,key) or 0 for r,_ in run_rows) for key in ("tikhub_raw_count","cli_raw_count","merged_count","within_week_count","eligible_like_count","filtered_count","final_count","displayable_count")};rejections={}
    current_eligibility=eligibility_clause(utcnow())
    funnel["unique_ingested_today_count"]=(await db.scalar(select(func.count(func.distinct(XhsNoteDiscovery.note_id))).join(XhsNote,XhsNote.id==XhsNoteDiscovery.note_id).where(XhsNoteDiscovery.discovered_at>=day_start,current_eligibility,XhsNote.quality_status.in_(PUBLIC_STATUSES)))) or 0
    funnel["current_daily_displayable_count"]=(await db.scalar(select(func.count(XhsNote.id)).where(XhsNote.published_at>=utcnow()-timedelta(hours=24),XhsNote.like_count>DAILY_MIN_LIKES_EXCLUSIVE,XhsNote.quality_status.in_(PUBLIC_STATUSES)))) or 0
    funnel["current_displayable_count"]=(await db.scalar(select(func.count(XhsNote.id)).where(current_eligibility,XhsNote.quality_status.in_(PUBLIC_STATUSES)))) or 0
    funnel["cli_missing_diagnostics_count"]=sum(r.run_source=="local_agent" and not (r.rejection_counts or {}).get("_search_diagnostics") for r,_ in run_rows)
    funnel["cli_diagnostics_count"]=sum(bool((r.rejection_counts or {}).get("_search_diagnostics")) for r,_ in run_rows)
    for r,_ in run_rows:
        for key,value in (r.rejection_counts or {}).items():
            if not key.startswith("_"):rejections[key]=rejections.get(key,0)+value
    image_open=(await db.scalar(select(func.count(XhsImageFailureReport.id)).where(XhsImageFailureReport.status=="open"))) or 0
    try:cli_version=version("xiaohongshu-cli")
    except PackageNotFoundError:cli_version=None
    base_total=sum(k.keyword_type=="base" and k.enabled for k in keywords);base_done=len({k.id for r,k in run_rows if k.keyword_type=="base" and r.status=="completed"})
    tikhub_health=health("tikhub");cli_health=health("cli");cookie_configured=Path(settings.XHS_CLI_COOKIE_FILE).is_file();auth_error=await cli_auth_error();cooldown_remaining=await cli_cooldown_remaining()
    alerts=[]
    if quota_data["used"]>=100:alerts.append({"level":"critical","message":"TikHub 已达到每日硬上限，付费请求已停止"})
    elif quota_data["used"]>=80:alerts.append({"level":"warning","message":"TikHub 今日调用已达到 80 次"})
    if image_open:alerts.append({"level":"warning" if image_open<20 else "critical","key":"image_failures","message":f"存在 {image_open} 条未处理图片失败报告"})
    for label,item in (("TikHub",tikhub_health),("CLI",cli_health)):
        if item["success_rate"] is not None and item["success_rate"]<70:alerts.append({"level":"critical" if item["success_rate"]<40 else "warning","message":f"{label} 最近 10 次成功率仅 {item['success_rate']}%"})
    if not cookie_configured:alerts.append({"level":"critical","key":"cli_auth","message":"xiaohongshu-cli 未授权，请扫码登录"})
    elif auth_error:alerts.append({"level":"critical","key":"cli_auth","message":"xiaohongshu-cli 登录已失效，已停止后续请求，请重新扫码"})
    elif cooldown_remaining:alerts.append({"level":"warning","key":"cli_cooldown","message":f"xiaohongshu-cli 触发验证码，约 {(cooldown_remaining+59)//60} 分钟后可重试；重新扫码可立即解除"})
    display_rate=(funnel["displayable_count"]/funnel["final_count"]*100) if funnel["final_count"] else 100
    if display_rate<90:alerts.append({"level":"critical" if display_rate<75 else "warning","message":f"合格素材最终可展示率仅 {display_rate:.1f}%"})
    if utcnow().hour>=23 and base_total and base_done<base_total:alerts.append({"level":"critical" if base_done/base_total<.8 else "warning","message":f"23:00 后基础词完成率为 {base_done/base_total*100:.1f}%"})
    pending6h=(await db.scalar(select(func.count(XhsNote.id)).where(XhsNote.detail_status.in_(["discovered","eligibility_check","hydrating","blocked_budget"]),XhsNote.created_at<utcnow()-timedelta(hours=6)))) or 0
    if pending6h>20:alerts.append({"level":"warning","message":f"超过 6 小时仍未补全的帖子有 {pending6h} 条"})
    keyword_data=[{"id":k.id,"keyword":k.keyword,"type":k.keyword_type,"group":k.schedule_group,"enabled":k.enabled,"lifecycle_status":k.lifecycle_status,"pinned":k.pinned,"zero_yield_streak":k.zero_yield_streak,"last_yield_count":k.last_yield_count,"quarantine_reason":k.quarantine_reason,"derived_evidence":k.derived_evidence or {},"cooldown_until":k.cooldown_until.isoformat() if k.cooldown_until else None,"next_run_at":k.next_run_at.isoformat() if k.next_run_at else None} for k in keywords]
    call_data=[{"id":c.id,"provider":c.provider,"operation":c.operation,"status":c.status,"is_paid":c.is_paid,"paid_request":bool(c.is_paid and c.request_count>0 and c.status not in ("blocked","skipped")),"request_count":c.request_count,"latency_ms":c.latency_ms,"estimated_cost":c.estimated_cost if c.status=="success" else 0,"error_code":c.error_code,"error_message":c.error_message,"created_at":c.created_at.isoformat()} for c in calls[:30]]
    return {"progress":{"base_completed":base_done,"base_total":base_total,"derived_completed":len({k.id for r,k in run_rows if k.keyword_type=="derived" and r.status=="completed"}),"derived_total":sum(k.keyword_type=="derived" and k.enabled for k in keywords)},"quota":quota_data,"providers":{"tikhub":tikhub_health,"cli":{**cli_health,"installed":bool(shutil.which(settings.XHS_CLI_BIN)),"version":cli_version,"version_ok":cli_version==settings.XHS_CLI_VERSION,"cookie_configured":cookie_configured,"auth_status":"expired" if auth_error else "configured" if cookie_configured else "missing","cookie_saved_at":cookie_saved_at(),"cooldown_minutes":settings.XHS_CLI_COOLDOWN_MINUTES,"cooldown_remaining_seconds":cooldown_remaining}},"funnel":funnel,"rejections":rejections,"image_health":{"open_reports":image_open,"missing":await db.scalar(select(func.count(XhsNote.id)).where(XhsNote.cover_url.is_(None))) or 0,"suspected_invalid":await db.scalar(select(func.count(XhsNote.id)).where(XhsNote.media_status=="suspected_invalid")) or 0},"runs":runs,"keywords":keyword_data,"alerts":alerts,"calls":call_data}


@admin_router.post("/cli-auth/sessions")
async def start_cli_auth(_admin:User=Depends(get_current_super_admin_user)):
    try:return await asyncio.to_thread(qr_login_manager.start)
    except Exception as exc:raise HTTPException(502,f"无法创建小红书登录二维码：{str(exc)[:300] or type(exc).__name__}")


@admin_router.get("/cli-auth/sessions/{session_id}")
async def poll_cli_auth(session_id:str,admin:User=Depends(get_current_super_admin_user),db:AsyncSession=Depends(get_db)):
    result=await asyncio.to_thread(qr_login_manager.poll,session_id)
    if result.get("status")=="authenticated":
        await clear_cli_auth_blocks()
        db.add(AdminAuditLog(actor_user_id=admin.id,action="xhs_cli_qr_login",target_type="xhs_cli",summary="重新扫码授权小红书 CLI",metadata_json={"user_id":result.get("user_id")}));await db.commit()
    return result


@admin_router.delete("/cli-auth/sessions/{session_id}")
async def cancel_cli_auth(session_id:str,_admin:User=Depends(get_current_super_admin_user)):
    return {"cancelled":await asyncio.to_thread(qr_login_manager.cancel,session_id)}


class KeywordBody(BaseModel):
    keyword:str=Field(...,min_length=1,max_length=120)
    schedule_group:int=Field(1,ge=1,le=3)


@admin_router.post("/keywords")
async def add_keyword(body:KeywordBody,admin:User=Depends(get_current_super_admin_user),db:AsyncSession=Depends(get_db)):
    normalized=" ".join(body.keyword.strip().lower().split())
    if await db.scalar(select(XhsKeyword.id).where(XhsKeyword.normalized_keyword==normalized)):raise HTTPException(409,"关键词已存在")
    row=XhsKeyword(keyword=body.keyword.strip(),normalized_keyword=normalized,keyword_type="base",schedule_group=body.schedule_group,enabled=True,lifecycle_status="active",lifecycle_started_at=utcnow());db.add(row);db.add(AdminAuditLog(actor_user_id=admin.id,action="xhs_keyword_create",target_type="xhs_keyword",summary=f"新增基础词 {body.keyword}",metadata_json={"group":body.schedule_group}));await db.commit();return {"id":row.id}


@admin_router.patch("/keywords/{keyword_id}/enabled")
async def toggle_keyword(keyword_id:int,enabled:bool,admin:User=Depends(get_current_super_admin_user),db:AsyncSession=Depends(get_db)):
    row=await db.get(XhsKeyword,keyword_id)
    if not row:raise HTTPException(404,"关键词不存在")
    row.enabled=enabled;row.lifecycle_status="active" if enabled else "quarantined";row.quarantine_reason=None if enabled else "管理员手动停用"
    db.add(AdminAuditLog(actor_user_id=admin.id,action="xhs_keyword_toggle",target_type="xhs_keyword",target_id=str(keyword_id),summary=f"{'启用' if enabled else '停用'} {row.keyword}",metadata_json={}));await db.commit();return {"enabled":enabled,"lifecycle_status":row.lifecycle_status}


@admin_router.patch("/keywords/{keyword_id}/pin")
async def pin_keyword(keyword_id:int,pinned:bool,admin:User=Depends(get_current_super_admin_user),db:AsyncSession=Depends(get_db)):
    row=await db.get(XhsKeyword,keyword_id)
    if not row: raise HTTPException(404,"关键词不存在")
    row.pinned=pinned;db.add(AdminAuditLog(actor_user_id=admin.id,action="xhs_keyword_pin",target_type="xhs_keyword",target_id=str(keyword_id),summary=f"{'置顶' if pinned else '取消置顶'} {row.keyword}",metadata_json={}));await db.commit();return {"pinned":pinned}


@admin_router.post("/keywords/{keyword_id}/restore")
async def restore_keyword(keyword_id:int,admin:User=Depends(get_current_super_admin_user),db:AsyncSession=Depends(get_db)):
    row=await db.get(XhsKeyword,keyword_id)
    if not row: raise HTTPException(404,"关键词不存在")
    active=(await db.scalar(select(func.count(XhsKeyword.id)).where(XhsKeyword.enabled.is_(True),XhsKeyword.lifecycle_status.in_(("active","trial"))))) or 0
    if active>=30: raise HTTPException(409,"当前已启用 30 个关键词，请先停用一个关键词")
    row.enabled=True;row.lifecycle_status="trial";row.zero_yield_streak=0;row.quarantine_reason=None;row.trial_started_at=utcnow()
    db.add(AdminAuditLog(actor_user_id=admin.id,action="xhs_keyword_restore",target_type="xhs_keyword",target_id=str(keyword_id),summary=f"恢复试采 {row.keyword}",metadata_json={}));await db.commit();return {"restored":True,"lifecycle_status":"trial"}


class KeywordRenameBody(BaseModel):
    keyword:str=Field(...,min_length=1,max_length=120)


@admin_router.patch("/keywords/{keyword_id}")
async def rename_keyword(keyword_id:int,body:KeywordRenameBody,admin:User=Depends(get_current_super_admin_user),db:AsyncSession=Depends(get_db)):
    row=await db.get(XhsKeyword,keyword_id)
    if not row:raise HTTPException(404,"关键词不存在")
    normalized=" ".join(body.keyword.strip().lower().split())
    if not normalized:raise HTTPException(422,"关键词不能为空")
    if await db.scalar(select(XhsKeyword.id).where(XhsKeyword.normalized_keyword==normalized,XhsKeyword.id!=keyword_id)):raise HTTPException(409,"关键词已存在")
    old=row.keyword;row.keyword=body.keyword.strip();row.normalized_keyword=normalized
    db.add(AdminAuditLog(actor_user_id=admin.id,action="xhs_keyword_rename",target_type="xhs_keyword",target_id=str(keyword_id),summary=f"关键词 {old} 修改为 {row.keyword}",metadata_json={"old":old,"new":row.keyword}));await db.commit();return {"id":row.id,"keyword":row.keyword}


@admin_router.post("/keywords/{keyword_id}/promote")
async def promote(keyword_id:int,admin:User=Depends(get_current_super_admin_user),db:AsyncSession=Depends(get_db)):
    row=await db.get(XhsKeyword,keyword_id)
    if not row:raise HTTPException(404,"关键词不存在")
    row.keyword_type="base";row.schedule_group=row.schedule_group or 1;row.cooldown_until=None;db.add(AdminAuditLog(actor_user_id=admin.id,action="xhs_keyword_promote",target_type="xhs_keyword",target_id=str(keyword_id),summary=f"动态词提升为基础词 {row.keyword}",metadata_json={}));await db.commit();return {"promoted":True}


@admin_router.delete("/keywords/{keyword_id}")
async def delete_keyword(keyword_id:int,admin:User=Depends(get_current_super_admin_user),db:AsyncSession=Depends(get_db)):
    row=await db.get(XhsKeyword,keyword_id)
    if not row:raise HTTPException(404,"关键词不存在")
    name=row.keyword;await db.delete(row)
    db.add(AdminAuditLog(actor_user_id=admin.id,action="xhs_keyword_delete",target_type="xhs_keyword",target_id=str(keyword_id),summary=f"删除关键词 {name}（执行记录与素材关联级联删除，已入库素材保留）",metadata_json={"keyword":name}));await db.commit();return {"deleted":True}


@admin_router.get("/image-failures")
async def list_image_failures(admin:User=Depends(require_admin_permission("monitoring:read")),db:AsyncSession=Depends(get_db)):
    rows=(await db.execute(select(XhsImageFailureReport,XhsNote).join(XhsNote,XhsNote.id==XhsImageFailureReport.note_id).where(XhsImageFailureReport.status=="open").order_by(XhsImageFailureReport.last_failed_at.desc()).limit(100))).all()
    return {"reports":[{"id":r.id,"note_id":n.note_id,"title":n.title,"image_kind":r.image_kind,"failed_url":r.failed_url,"failure_count":r.failure_count,"last_failed_at":r.last_failed_at.isoformat()} for r,n in rows]}


@admin_router.get("/runs/{run_id}/notes")
async def run_notes(run_id:int,admin:User=Depends(require_admin_permission("monitoring:read")),db:AsyncSession=Depends(get_db)):
    run=await db.get(XhsKeywordRun,run_id)
    if not run:raise HTTPException(404,"采集运行不存在")
    keyword=await db.get(XhsKeyword,run.keyword_id)
    rows=(await db.execute(select(XhsNoteDiscovery,XhsNote).join(XhsNote,XhsNote.id==XhsNoteDiscovery.note_id).where(XhsNoteDiscovery.run_id==run_id))).all()
    grouped={}
    for d,n in rows:
        item=grouped.setdefault(n.id,{"note_id":n.note_id,"title":n.title,"author":n.author_nickname,"like_count":n.like_count,"published_at":n.published_at.isoformat() if n.published_at else None,"status":n.quality_status,"stable_url":n.stable_url,"original_url":original_note_url(n),"providers":[]})
        item["providers"].append({"provider":d.provider,"rank":d.provider_rank})
    return {"run":run_payload(run,keyword),"notes":sorted(grouped.values(),key=lambda x:x["like_count"] or 0,reverse=True)}


@admin_router.post("/image-failures/{report_id}/resolve")
async def resolve_image_failure(report_id:int,admin:User=Depends(require_admin_permission("monitoring:read")),db:AsyncSession=Depends(get_db)):
    row=await db.get(XhsImageFailureReport,report_id)
    if not row:raise HTTPException(404,"报告不存在")
    row.status="resolved";db.add(AdminAuditLog(actor_user_id=admin.id,action="xhs_image_failure_resolve",target_type="xhs_image_failure_report",target_id=str(report_id),summary=f"标记图片失败报告已处理（{row.image_kind}）",metadata_json={"note_id":row.note_id,"image_kind":row.image_kind}));await db.commit();return {"resolved":True}


@admin_router.post("/keywords/{keyword_id}/retry-free",status_code=202)
async def retry_free(keyword_id:int,force:bool=False,admin:User=Depends(require_admin_permission("tasks:retry")),db:AsyncSession=Depends(get_db)):
    run=(await db.execute(select(XhsKeywordRun).where(XhsKeywordRun.keyword_id==keyword_id,XhsKeywordRun.run_date==utcnow().date()))).scalar_one_or_none()
    if run and run.status=="completed" and not force:raise HTTPException(409,"成功完成的关键词当天不允许再次搜索")
    task=collect_keyword_task.apply_async(args=[keyword_id,False,True]);db.add(AdminAuditLog(actor_user_id=admin.id,action="xhs_retry_free",target_type="xhs_keyword",target_id=str(keyword_id),summary="小红书免费链路重试",metadata_json={"task_id":task.id}));await db.commit();return {"task_id":task.id,"paid":False}


@admin_router.post("/keywords/{keyword_id}/retry-paid",status_code=202)
async def retry_paid(keyword_id:int,admin:User=Depends(get_current_super_admin_user),db:AsyncSession=Depends(get_db)):
    run=(await db.execute(select(XhsKeywordRun).where(XhsKeywordRun.keyword_id==keyword_id,XhsKeywordRun.run_date==utcnow().date()))).scalar_one_or_none()
    if run and run.status=="completed":raise HTTPException(409,"成功完成的关键词当天不允许再次搜索")
    task=collect_keyword_task.apply_async(args=[keyword_id,True,True]);db.add(AdminAuditLog(actor_user_id=admin.id,action="xhs_retry_paid",target_type="xhs_keyword",target_id=str(keyword_id),summary="最高管理员确认 TikHub 付费重试",metadata_json={"task_id":task.id}));await db.commit();return {"task_id":task.id,"paid":True}


@admin_router.post("/notes/{note_id}/refresh-image-free",status_code=202)
async def refresh_image_free(note_id:str,admin:User=Depends(require_admin_permission("tasks:retry")),db:AsyncSession=Depends(get_db)):
    task=refresh_note_image_task.apply_async(args=[note_id,False]);db.add(AdminAuditLog(actor_user_id=admin.id,action="xhs_image_refresh_free",target_type="xhs_note",target_id=note_id,summary="免费刷新远程图片 URL",metadata_json={"task_id":task.id,"auto_paid":False}));await db.commit();return {"task_id":task.id,"paid":False}


@admin_router.post("/notes/{note_id}/refresh-image-paid",status_code=202)
async def refresh_image_paid(note_id:str,admin:User=Depends(get_current_super_admin_user),db:AsyncSession=Depends(get_db)):
    task=refresh_note_image_task.apply_async(args=[note_id,True]);db.add(AdminAuditLog(actor_user_id=admin.id,action="xhs_image_refresh_paid",target_type="xhs_note",target_id=note_id,summary="最高管理员确认 TikHub 图片刷新",metadata_json={"task_id":task.id}));await db.commit();return {"task_id":task.id,"paid":True}

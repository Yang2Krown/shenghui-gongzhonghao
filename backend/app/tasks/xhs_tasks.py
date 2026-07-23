"""小红书关键词采集、补全和动态词 Celery 任务。"""
import asyncio
import logging
import random
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from celery import shared_task
from sqlalchemy import select

from app.core.config import settings
from app.core.timezone import utcnow
from app.db.session import AsyncSessionLocal, SessionLocal, engine as async_engine
from app.models.xhs import XhsKeyword, XhsNote, XhsNoteDiscovery, XhsProviderCall
from app.services.llm.llm_client import ChatMessage, get_llm_client
from app.services.xhs_collection import collect_keyword, eligibility_clause, normalize_keyword, refresh_note_image, reserve_tikhub_searches
from app.services.xhs_topics import evaluate_keyword_lifecycle, rebuild_semantic_topics

logger = logging.getLogger(__name__)
PUBLIC_XHS_STATUSES = ("ready", "ready_degraded", "synced")


@shared_task(name="xhs.collect_keyword")
def collect_keyword_task(keyword_id: int, allow_paid: bool = True, retry_existing: bool = False):
    if not settings.XHS_SERVER_COLLECTION_ENABLED: return {"skipped": True, "reason": "server_collection_disabled"}
    with SessionLocal() as db: return asyncio.run(collect_keyword(db, keyword_id, allow_paid=allow_paid, retry_existing=retry_existing))


@shared_task(name="xhs.refresh_note_image")
def refresh_note_image_task(note_id: str, allow_paid: bool = False):
    with SessionLocal() as db:return asyncio.run(refresh_note_image(db,note_id,allow_paid=allow_paid))


@shared_task(name="xhs.cache_note_media", bind=True, max_retries=3)
def cache_note_media_task(self, note_id: str):
    """趁小红书 CDN URL 仍有效时预缓存；只写服务器本地盘，不上传 OSS。

    CDN URL 短时效，失败时指数退避重试几次（而非静默丢弃），降低封面失败率。
    """
    from app.api.v1.xhs import fetch_media_to_cache, media_cache_base, media_cache_lookup_exact
    from app.models.xhs import XhsNote
    with SessionLocal() as db:
        note=db.scalar(select(XhsNote).where(XhsNote.note_id==note_id))
        if not note:return {"cached":0,"failed":0,"reason":"素材不存在"}
        cached=failed=0
        for kind,url in (("cover",note.cover_url),("avatar",note.avatar_url)):
            if not url or media_cache_lookup_exact(note.id,kind,url):continue
            try:
                asyncio.run(fetch_media_to_cache(url,media_cache_base(note.id,kind,url)));cached+=1
            except Exception as exc:
                failed+=1
                logger.info("小红书媒体预缓存失败 note=%s kind=%s: %s",note_id,kind,exc)
        # 两个 kind 都试过之后，若仍有失败则指数退避重试整则任务（已缓存的会被
        # lookup_exact 跳过）。重试耗尽后抛错，让失败可见而不是静默吞掉。
        if failed:
            raise self.retry(countdown=60*(2**self.request.retries),exc=RuntimeError(f"note {note_id} 有 {failed} 个媒体预缓存失败"))
        return {"cached":cached,"failed":failed}


@shared_task(name="xhs.warm_media_cache")
def warm_media_cache_task(days: int = 7, limit: int = 300, max_fetch: int = 120):
    """周期性自愈：为「可展示且近 N 天」的素材补齐缺失的封面/头像缓存。

    封面失败的根因是媒体懒加载——只有查看时才拉取，而 xhscdn 签名 URL 早已过期。
    本任务周期性把仍缺缓存的素材趁 URL 相对新鲜时预取，把「一次性尽力而为」变成
    「自愈」。与 cleanup_media_cache 用同一 keep 集合逻辑，互为镜像。

    max_fetch 是单次实际回源拉取的硬上限：已缓存的直接跳过，真正发请求的通常只有
    漏网几张；该上限防止历史积压一次性打向 CDN，避免触发风控。
    """
    from app.api.v1.xhs import fetch_media_to_cache, media_cache_base, media_cache_lookup_exact
    cutoff=utcnow()-timedelta(days=max(1,days))
    with SessionLocal() as db:
        # 最新优先：刚入库的 URL 最新鲜、最该先补；旧 URL 多半已过期，补了也易失败。
        notes=db.scalars(select(XhsNote).where(
            XhsNote.quality_status.in_(PUBLIC_XHS_STATUSES),
            XhsNote.published_at.is_not(None),
            XhsNote.published_at>=cutoff,
        ).order_by(XhsNote.id.desc()).limit(limit)).all()
        warmed=skipped=failed=0
        for note in notes:
            for kind,url in (("cover",note.cover_url),("avatar",note.avatar_url)):
                if not url or media_cache_lookup_exact(note.id,kind,url):
                    skipped+=1;continue
                if warmed+failed>=max_fetch:
                    continue
                try:
                    asyncio.run(fetch_media_to_cache(url,media_cache_base(note.id,kind,url)));warmed+=1
                except Exception as exc:
                    failed+=1
                    logger.info("小红书媒体周期预热失败 note=%s kind=%s: %s",note.note_id,kind,exc)
        if warmed+failed>=max_fetch:
            logger.info("小红书媒体预热达单次拉取上限 max_fetch=%d，剩余留待下一周期", max_fetch)
        return {"notes":len(notes),"warmed":warmed,"skipped":skipped,"failed":failed}


def purge_xhs_media_cache_files(cache_dir: Path, keep_note_ids: set[int]) -> dict:
    """删除不再展示的素材图片；文件名首段是 XhsNote 数据库主键。"""
    deleted_files=deleted_bytes=0
    if not cache_dir.is_dir():return {"deleted_files":0,"deleted_bytes":0}
    for path in cache_dir.iterdir():
        if not path.is_file():continue
        try:note_pk=int(path.name.split("_",1)[0])
        except (ValueError,IndexError):continue
        if note_pk in keep_note_ids:continue
        try:
            deleted_bytes+=path.stat().st_size
            path.unlink()
            deleted_files+=1
        except FileNotFoundError:pass
    return {"deleted_files":deleted_files,"deleted_bytes":deleted_bytes}


@shared_task(name="xhs.cleanup_media_cache")
def cleanup_xhs_media_cache_task(days: int = 7):
    """每日只保留仍会在前端展示的近 N 天小红书素材图片。"""
    cutoff=utcnow()-timedelta(days=max(1,days))
    with SessionLocal() as db:
        keep_ids=set(db.scalars(select(XhsNote.id).where(
            XhsNote.quality_status.in_(PUBLIC_XHS_STATUSES),
            XhsNote.published_at.is_not(None),
            XhsNote.published_at>=cutoff,
        )).all())
    cache_dir=Path(settings.UPLOAD_DIR)/"xhs_media"
    return {**purge_xhs_media_cache_files(cache_dir,keep_ids),"kept_notes":len(keep_ids),"days":days}


@shared_task(name="xhs.dispatch_group")
def dispatch_group_task(group: int):
    if not settings.XHS_SERVER_COLLECTION_ENABLED: return {"skipped": True, "reason": "server_collection_disabled"}
    with SessionLocal() as db:
        rows=db.scalars(select(XhsKeyword).where(XhsKeyword.enabled.is_(True),XhsKeyword.keyword_type=="base",XhsKeyword.schedule_group==group).order_by(XhsKeyword.id)).all()
        reserve_tikhub_searches(db,len(rows))
        for index,row in enumerate(rows): collect_keyword_task.apply_async(args=[row.id],countdown=index*90+random.randint(10,30))
        return {"group":group,"dispatched":len(rows)}


@shared_task(name="xhs.dispatch_derived")
def dispatch_derived_task():
    if not settings.XHS_SERVER_COLLECTION_ENABLED: return {"skipped": True, "reason": "server_collection_disabled"}
    today=utcnow().date()
    with SessionLocal() as db:
        rows=db.scalars(select(XhsKeyword).where(XhsKeyword.enabled.is_(True),XhsKeyword.keyword_type=="derived",(XhsKeyword.cooldown_until.is_(None)) | (XhsKeyword.cooldown_until<=today)).order_by(XhsKeyword.id).limit(5)).all()
        reserve_tikhub_searches(db,len(rows))
        for index,row in enumerate(rows): collect_keyword_task.apply_async(args=[row.id],countdown=index*90+random.randint(10,30))
        return {"dispatched":len(rows)}


async def _normalize_dynamic(candidates: list[str]) -> list[str]:
    if not candidates: return []
    try:
        client=get_llm_client()
        prompt="将这些小红书 AI 趋势词去重归一化，保留具体可搜索短语，排除 AI、工具等泛词，最多返回 5 个。仅返回 JSON：{\"keywords\":[...]}.\n"+"\n".join(candidates[:20])
        result=await client.chat([ChatMessage(role="user",content=prompt)],temperature=.1,max_tokens=400,json_mode=True)
        return [str(x).strip() for x in (result.parsed or {}).get("keywords",[]) if str(x).strip()][:5]
    except Exception as exc:
        logger.warning("动态词 AI 归一化不可用，使用确定性归一化: %s",exc)
        return candidates[:5]


@shared_task(name="xhs.generate_dynamic_keywords")
def generate_dynamic_keywords_task():
    """仅使用 72 小时内合格基础词帖子；至少 3 帖、2 作者，结果次日执行。"""
    if not settings.XHS_COLLECTION_ENABLED: return {"skipped":True,"reason":"feature_disabled"}
    cutoff=utcnow()-timedelta(hours=72);generic={"ai","工具","人工智能","教程","分享","干货"}
    with SessionLocal() as db:
        rows=db.execute(select(XhsNote,XhsKeyword).join(XhsNoteDiscovery,XhsNoteDiscovery.note_id==XhsNote.id).join(XhsKeyword,XhsKeyword.id==XhsNoteDiscovery.keyword_id).where(XhsKeyword.keyword_type=="base",XhsNote.quality_status.in_(["ready","ready_degraded","synced"]),XhsNote.published_at>=cutoff,eligibility_clause(utcnow()))).all()
        posts=defaultdict(set);authors=defaultdict(set)
        for note,_keyword in rows:
            for tag in list(note.native_tags or [])+list(note.ai_topics or []):
                key=normalize_keyword(str(tag).lstrip("#"));
                if len(key)<2 or key in generic: continue
                posts[key].add(note.id);authors[key].add(note.author_id or note.author_nickname)
        existing={x for x in db.scalars(select(XhsKeyword.normalized_keyword)).all()}
        ranked=[k for k in sorted(posts,key=lambda x:(len(posts[x]),len(authors[x])),reverse=True) if len(posts[k])>=3 and len(authors[k])>=2 and k not in existing][:20]
        normalized=asyncio.run(_normalize_dynamic(ranked))
        created=[];tomorrow=utcnow().date()+timedelta(days=1)
        for value in normalized[:5]:
            key=normalize_keyword(value)
            if key in existing or key in generic: continue
            db.add(XhsKeyword(keyword=value,normalized_keyword=key,keyword_type="derived",enabled=False,lifecycle_status="candidate",derived_evidence={"post_count":len(posts.get(key,set())),"author_count":len(authors.get(key,set())),"generated_at":utcnow().isoformat()},next_run_at=None))
            existing.add(key);created.append(value)
        db.commit();return {"candidates":len(ranked),"created":created,"run_date":tomorrow.isoformat()}


@shared_task(name="xhs.analyze_notes")
def analyze_notes_task():
    """每批 10 篇生成中文摘要和 3-5 个话题；失败不影响展示。"""
    if not settings.XHS_COLLECTION_ENABLED: return {"skipped":True,"reason":"feature_disabled"}
    async def run():
        await async_engine.dispose()
        try:
            with SessionLocal() as db:
                notes=db.scalars(select(XhsNote).where(XhsNote.quality_status.in_(["ready","ready_degraded","synced"]),XhsNote.ai_summary.is_(None)).order_by(XhsNote.id).limit(100)).all();done=0
                for start in range(0,len(notes),10):
                    batch=notes[start:start+10]
                    try:
                        client=get_llm_client();payload=[{"note_id":n.note_id,"title":n.title,"content":(n.content or "")[:1500]} for n in batch]
                        result=await client.chat([ChatMessage(role="user",content="为每篇小红书笔记输出中文摘要和3到5个具体AI话题。返回 JSON：{\"items\":[{\"note_id\":\"\",\"summary\":\"\",\"topics\":[]}]}\n"+str(payload))],temperature=.2,max_tokens=1800,json_mode=True)
                        by_id={str(x.get("note_id")):x for x in (result.parsed or {}).get("items",[])}
                        for n in batch:
                            item=by_id.get(n.note_id)
                            if item:n.ai_summary=str(item.get("summary") or "")[:2000];n.ai_topics=[str(x) for x in (item.get("topics") or [])][:5];done+=1
                        db.add(XhsProviderCall(provider="llm",operation="xhs_topic_extract",status="success",is_paid=True,request_count=1,estimated_cost=0,metadata_json={"batch_size":len(batch)}));db.commit()
                    except Exception as exc: logger.warning("小红书分析批次失败，不影响素材展示: %s",exc);db.rollback()
                return {"selected":len(notes),"analyzed":done}
        finally:
            await async_engine.dispose()
    return asyncio.run(run())


@shared_task(name="xhs.rebuild_semantic_topics")
def rebuild_semantic_topics_task(wave: str = "nightly"):
    async def run():
        await async_engine.dispose()
        try:
            async with AsyncSessionLocal() as db: return await rebuild_semantic_topics(db,wave)
        finally:
            await async_engine.dispose()
    return asyncio.run(run())


@shared_task(name="xhs.evaluate_keyword_lifecycle")
def evaluate_keyword_lifecycle_task():
    async def run():
        async with AsyncSessionLocal() as db: return await evaluate_keyword_lifecycle(db)
    return asyncio.run(run())

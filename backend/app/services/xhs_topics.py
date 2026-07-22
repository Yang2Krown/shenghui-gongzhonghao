"""XHS semantic topic clustering, trend snapshots and keyword lifecycle."""
from __future__ import annotations

import math
from collections import Counter, deque
from datetime import date, timedelta

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import utcnow
from app.models.xhs import (
    XhsKeyword, XhsKeywordRun, XhsNote, XhsSemanticTopic, XhsTopicMember,
    XhsTopicSnapshot,
)
from app.services.llm.embedding_service import embedding_service
from app.services.xhs_collection import eligibility_clause

PUBLIC_STATUSES = ("ready", "ready_degraded", "synced")
COSINE_EPS = .22
AVERAGE_LINK_SIMILARITY = .66
STABLE_TOPIC_SIMILARITY = .82


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right): return 0.0
    dot=sum(a*b for a,b in zip(left,right)); ln=math.sqrt(sum(a*a for a in left)); rn=math.sqrt(sum(b*b for b in right))
    return dot/(ln*rn) if ln and rn else 0.0


def dbscan(vectors: list[list[float]], eps: float = COSINE_EPS, min_samples: int = 2) -> list[list[int]]:
    """Small deterministic cosine DBSCAN; -1/noise notes remain available in All."""
    neighbors=[[j for j,other in enumerate(vectors) if 1-cosine_similarity(vec,other)<=eps] for vec in vectors]
    labels=[None]*len(vectors); cluster_id=0
    for index in range(len(vectors)):
        if labels[index] is not None: continue
        if len(neighbors[index])<min_samples: labels[index]=-1; continue
        labels[index]=cluster_id; queue=deque(neighbors[index])
        while queue:
            current=queue.popleft()
            if labels[current]==-1: labels[current]=cluster_id
            if labels[current] is not None: continue
            labels[current]=cluster_id
            if len(neighbors[current])>=min_samples: queue.extend(neighbors[current])
        cluster_id+=1
    return [[i for i,label in enumerate(labels) if label==cid] for cid in range(cluster_id)]


def semantic_clusters(vectors: list[list[float]], threshold: float = AVERAGE_LINK_SIMILARITY) -> list[list[int]]:
    """Average-link clustering avoids DBSCAN's semantic chaining across broad AI posts."""
    groups=[[index] for index in range(len(vectors))]
    while True:
        best=(-1.0,None,None)
        for left in range(len(groups)):
            for right in range(left+1,len(groups)):
                similarities=[cosine_similarity(vectors[a],vectors[b]) for a in groups[left] for b in groups[right]]
                score=sum(similarities)/len(similarities)
                if score>best[0]:best=(score,left,right)
        if best[1] is None or best[0]<threshold:break
        _,left,right=best
        groups[left].extend(groups[right]);groups.pop(right)
    return [group for group in groups if len(group)>=2]


def _note_text(note: XhsNote) -> str:
    tags=" ".join(str(x) for x in (note.native_tags or []))
    return "\n".join(x for x in ((note.title or "").strip(),(note.content or "")[:3000].strip(),tags,(note.ai_summary or "").strip()) if x)[:6000]


def _centroid(vectors: list[list[float]]) -> list[float]:
    return [sum(values)/len(vectors) for values in zip(*vectors)] if vectors else []


def _topic_label(notes: list[XhsNote]) -> str:
    candidates=[]
    for note in notes:
        candidates.extend(str(x).strip().lstrip("#") for x in (note.ai_topics or [])+(note.native_tags or []))
    useful=[x for x in candidates if 2<=len(x)<=24 and x.lower() not in {"ai","人工智能","工具","分享","教程"}]
    if useful: return Counter(useful).most_common(1)[0][0]
    return next(((n.title or "").strip()[:36] for n in notes if (n.title or "").strip()),"未命名话题")


async def _synthesize_topic_labels(groups: list[list[XhsNote]]) -> dict[int,dict[str,str]]:
    """Use the shared meaning of each content cluster to write a concrete editorial topic."""
    if not groups:return {}
    try:
        from app.services.llm.llm_client import ChatMessage, get_llm_client
        samples=[]
        for index,notes in enumerate(groups):
            samples.append({
                "cluster":index,
                "articles":[{"title":n.title,"summary":n.ai_summary or (n.content or "")[:220]} for n in sorted(notes,key=lambda item:item.like_count or 0,reverse=True)[:5]],
            })
        prompt=(
            "根据每组文章共同讨论的具体事件、产品变化或创作现象，提炼中文小话题。"
            "禁止把搜索关键词、宽泛标签（如AI、AIGC、大模型、agent、codex）直接当话题名；"
            "名称需具体到发生了什么，8到22字；摘要不超过45字。"
            "返回JSON：{\"items\":[{\"cluster\":0,\"name\":\"\",\"summary\":\"\"}]}\n"+str(samples)
        )
        result=await get_llm_client().chat([ChatMessage(role="user",content=prompt)],temperature=.2,max_tokens=1800,json_mode=True)
        output={}
        for item in (result.parsed or {}).get("items",[]):
            index=int(item.get("cluster",-1));name=str(item.get("name") or "").strip()[:80];summary=str(item.get("summary") or "").strip()[:300]
            if 0<=index<len(groups) and name:output[index]={"name":name,"summary":summary}
        return output
    except Exception:
        return {}


async def rebuild_semantic_topics(db: AsyncSession, wave: str = "nightly") -> dict:
    now=utcnow()
    notes=(await db.scalars(select(XhsNote).where(eligibility_clause(now),XhsNote.quality_status.in_(PUBLIC_STATUSES),func.length(func.coalesce(XhsNote.title,"")+func.coalesce(XhsNote.content,""))>0).order_by(XhsNote.id))).all()
    missing=[n for n in notes if not n.topic_embedding]
    if missing:
        embeddings=await embedding_service.embed_batch([_note_text(n) for n in missing])
        for note,vector in zip(missing,embeddings):
            if vector: note.topic_embedding=vector; note.semantic_analyzed_at=now
        await db.flush()
    usable=[n for n in notes if n.topic_embedding]
    clusters=semantic_clusters([list(n.topic_embedding) for n in usable])
    member_groups=[[usable[i] for i in indices] for indices in clusters]
    synthesized=await _synthesize_topic_labels(member_groups)
    existing=(await db.scalars(select(XhsSemanticTopic).where(XhsSemanticTopic.status=="active"))).all()
    used_topics:set[int]=set(); touched=[]
    # Rebuild current membership from the two level rules. A daily note with
    # 201-2000 likes must not remain in a weekly topic after it becomes >24h old.
    await db.execute(delete(XhsTopicMember))
    for cluster_index,indices in enumerate(clusters):
        members=member_groups[cluster_index]; centroid=_centroid([list(n.topic_embedding) for n in members])
        label=synthesized.get(cluster_index,{})
        name=label.get("name") or _topic_label(members);summary=label.get("summary") or next((n.ai_summary for n in members if n.ai_summary),None)
        matches=[(cosine_similarity(centroid,list(t.centroid or [])),t) for t in existing if t.id not in used_topics]
        score,topic=max(matches,default=(0,None),key=lambda item:item[0])
        first=min(n.first_discovered_at for n in members);last=max(n.last_discovered_at for n in members)
        if topic is None or score<STABLE_TOPIC_SIMILARITY:
            topic=XhsSemanticTopic(name=name,summary=summary,centroid=centroid,first_seen_at=first,last_seen_at=last,active_days=1)
            db.add(topic); await db.flush()
        else:
            topic.name=name;topic.summary=summary; topic.centroid=centroid; topic.first_seen_at=min(topic.first_seen_at,first); topic.last_seen_at=last
        observed_days={day for n in members for day in (n.first_discovered_at.date(),n.last_discovered_at.date())}
        topic.active_days=len(observed_days);used_topics.add(topic.id)
        for note in members: db.add(XhsTopicMember(topic_id=topic.id,note_id=note.id,similarity=cosine_similarity(centroid,list(note.topic_embedding)),assigned_at=now))
        touched.append((topic,members))
    for topic in existing:
        if topic.id not in used_topics: topic.status="inactive"
    await db.flush()

    raw=[]
    for topic,members in touched:
        day_start=now.replace(hour=0,minute=0,second=0,microsecond=0)
        recent=[n for n in members if n.last_discovered_at>=day_start]
        authors={n.author_id or n.author_nickname for n in members if n.author_id or n.author_nickname}; recent_authors={n.author_id or n.author_nickname for n in recent if n.author_id or n.author_nickname}
        engagement=sum((n.like_count or 0)+(n.collect_count or 0)+(n.comment_count or 0)+(n.share_count or 0) for n in members)
        previous=(await db.scalars(select(XhsTopicSnapshot).where(XhsTopicSnapshot.topic_id==topic.id).order_by(desc(XhsTopicSnapshot.snapshot_at)).limit(1))).first()
        growth=((engagement-(previous.engagement_total or 0))/max(1,previous.engagement_total)*100) if previous else 0
        raw.append({"topic":topic,"members":members,"new":len(recent),"new_authors":len(recent_authors),"engagement":engagement,"growth":growth,"authors":len(authors)})
    def normalized(key,item):
        values=[max(0,float(x[key])) for x in raw]; top=max(values,default=0)
        return max(0,float(item[key]))/top if top else 0
    for item in raw:
        topic=item["topic"]; longevity=min(topic.active_days,7)/7
        score=round(100*(.35*normalized("new",item)+.25*normalized("new_authors",item)+.25*normalized("growth",item)+.15*longevity),1)
        evidence=[f"近 7 日在 {topic.active_days} 个采集日出现",f"今日再次监测到 {item['new']} 篇",f"涉及 {item['authors']} 位作者"]
        if item["growth"]>0: evidence.append(f"互动较上次上涨 {item['growth']:.0f}%")
        snapshot=(await db.execute(select(XhsTopicSnapshot).where(XhsTopicSnapshot.topic_id==topic.id,XhsTopicSnapshot.snapshot_date==now.date(),XhsTopicSnapshot.wave==wave))).scalar_one_or_none()
        values=dict(snapshot_at=now,note_count=len(item["members"]),author_count=item["authors"],new_notes_24h=item["new"],new_authors_24h=item["new_authors"],engagement_total=item["engagement"],engagement_growth=item["growth"],fermentation_score=score,evidence=evidence)
        if snapshot:
            for key,value in values.items(): setattr(snapshot,key,value)
        else: db.add(XhsTopicSnapshot(topic_id=topic.id,snapshot_date=now.date(),wave=wave,**values))
    await db.commit()
    return {"selected":len(notes),"embedded":len(usable),"topics":len(touched),"wave":wave}


async def evaluate_keyword_lifecycle(db: AsyncSession, run_date: date | None = None) -> dict:
    """Keep the base pool stable; rotate summary words after three zero-yield days."""
    today=run_date or utcnow().date(); quarantined=[]; activated=[]
    keywords=(await db.scalars(select(XhsKeyword))).all()
    for keyword in keywords:
        if not keyword.enabled or keyword.lifecycle_status not in ("active","trial"): continue
        runs=(await db.scalars(select(XhsKeywordRun).where(XhsKeywordRun.keyword_id==keyword.id,XhsKeywordRun.run_date==today))).all()
        if not runs or any(run.status!="completed" for run in runs): continue
        produced=sum(run.final_count or 0 for run in runs); keyword.last_yield_count=produced
        keyword.zero_yield_streak=0 if produced else keyword.zero_yield_streak+1
        if keyword.keyword_type=="derived" and not produced and keyword.zero_yield_streak>=3 and not keyword.pinned:
            keyword.enabled=False; keyword.lifecycle_status="quarantined"; keyword.quarantine_reason="连续 3 个有效采集日无合格笔记"; quarantined.append(keyword.keyword)
        elif produced and keyword.lifecycle_status=="trial": keyword.lifecycle_status="active"
    active_count=sum(k.keyword_type=="derived" and k.enabled and k.lifecycle_status in ("active","trial") for k in keywords)
    candidates=sorted((k for k in keywords if k.lifecycle_status=="candidate"),key=lambda k:(-(k.derived_evidence or {}).get("post_count",0),k.id))
    for keyword in candidates[:max(0,5-active_count)]:
        keyword.enabled=True; keyword.lifecycle_status="trial"; keyword.trial_started_at=utcnow(); keyword.zero_yield_streak=0; activated.append(keyword.keyword)
    await db.commit()
    return {"date":today.isoformat(),"quarantined":quarantined,"activated":activated}

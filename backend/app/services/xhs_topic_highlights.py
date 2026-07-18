"""小红书选题看板 AI 亮点：DeepSeek 生成一句话选题亮点，Redis 缓存 12 小时。

缓存键含样本指纹（话题 + 样本数 + 各样本 note_id/点赞数），看板数据一变缓存自动失效。
LLM 未配置/调用失败/预算熔断、Redis 故障时一律降级为 None，绝不影响接口返回。
"""
import asyncio
import hashlib

import redis.asyncio as aioredis

from app.core.config import settings
from app.services.llm.llm_client import ChatMessage

CACHE_TTL_SECONDS=12*3600
SYSTEM_PROMPT="你是中文新媒体编辑，帮公众号作者提炼小红书选题亮点。"


def _cache_key(board:dict)->str:
    fingerprint="|".join(f"{n.get('note_id')}:{n.get('likes')}" for n in board.get("notes") or [])
    raw=f"{board.get('topic')}|{board.get('sample_count')}|{fingerprint}"
    return "xhs:topic-hl:"+hashlib.sha1(raw.encode()).hexdigest()


def _build_prompt(board:dict,notes:list)->str:
    reps=sorted(notes,key=lambda n:getattr(n,"like_count",0) or 0,reverse=True)[:3]
    lines=[]
    for n in reps:
        content=(getattr(n,"content","") or "").replace("\n"," ")[:120]
        lines.append(f"- 《{getattr(n,'title','') or ''}》（{getattr(n,'like_count',0) or 0} 赞）：{content}")
    samples="\n".join(lines) or "（无）"
    return (f"小红书话题：{board.get('topic')}\n样本数：{board.get('sample_count')}，单篇最高赞：{board.get('max_likes')}\n"
            f"代表笔记：\n{samples}\n"
            "用一句话（不超过 40 字）向公众号作者介绍这个话题为什么值得写、可从什么角度切入，直接输出这句话，不要引号不要解释")


def _clean(text:str)->str|None:
    first=(text or "").strip().splitlines()[0].strip().strip("\"'“”‘’").strip()
    return first[:60] or None


async def _generate(board:dict,notes:list)->str|None:
    try:
        from app.services.llm.deepseek_client import DeepSeekClient  # 局部导入：未配置 API Key 时构造即抛错，且便于测试替换
        result=await DeepSeekClient().chat([ChatMessage(role="system",content=SYSTEM_PROMPT),ChatMessage(role="user",content=_build_prompt(board,notes))],temperature=0.5,max_tokens=120)
        return _clean(result.text)
    except Exception:  # 含 DEEPSEEK_API_KEY 未配置、网络失败、预算熔断
        return None


async def _highlight_for(board:dict,notes:list)->str|None:
    key=_cache_key(board);redis=None
    try:
        try:
            redis=aioredis.from_url(settings.CELERY_BROKER_URL,decode_responses=True)
            cached=await redis.get(key)
        except Exception:
            redis,cached=None,None  # 缓存故障直接跳过缓存逻辑，不影响生成
        if cached:return cached
        text=await _generate(board,notes)
        if text and redis is not None:
            try:await redis.set(key,text,ex=CACHE_TTL_SECONDS)
            except Exception:pass
        return text
    finally:
        if redis is not None:
            try:await redis.aclose()
            except Exception:pass


async def attach_highlights(boards:list[dict],note_map:dict[str,list]|None=None)->None:
    """原地给每个 board 加 ai_highlight（str|None）；note_map 为 topic->笔记对象列表（正文取自笔记对象）。"""
    note_map=note_map or {}
    results=await asyncio.gather(*(_highlight_for(b,note_map.get(b.get("topic"),[])) for b in boards),return_exceptions=True)
    for board,text in zip(boards,results):
        board["ai_highlight"]=text if isinstance(text,str) else None

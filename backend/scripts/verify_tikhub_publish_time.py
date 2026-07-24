"""一次性探针:验证 TikHub 返回的发布时间字段能否撑起 24h daily 档。

用法(在 backend/ 下,先 export TIKHUB_TOKEN=...):
    .venv/bin/python scripts/verify_tikhub_publish_time.py [关键词]

只读:不连数据库、不写 Redis、不经过 TikHubProvider 的并发槽/计费,
直接打原始 HTTP。真实调 TikHub,每次 search/detail 计一次费(免费额度内)。

回答的问题:xhs_collection.normalize_candidate 能否从 TikHub 的
search 卡片 / detail 里解出精确 published_at(dt_value 认得的时间戳),
从而把 24h daily 档完全交给 TikHub,不再依赖被风控的 CLI。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

# 复用生产解析逻辑,保证验证的就是线上真实会跑到的代码路径。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.xhs_collection import (  # noqa: E402
    dt_value,
    first,
    normalize_candidate,
    search_publish_time,
    unwrap_items,
)

API_BASE = os.environ.get("TIKHUB_API_BASE", "https://api.tikhub.io")
SEARCH_PATH = "/api/v1/xiaohongshu/app_v2/search_notes"
# 生产现用 web_v3;官方更推荐 app_v2。两个都探,横向对比时间字段。
DETAIL_PATH_WEB_V3 = "/api/v1/xiaohongshu/web_v3/fetch_note_detail"
DETAIL_PATH_APP_V2 = "/api/v1/xiaohongshu/app_v2/get_image_note_detail"

# 我们关心的时间/点赞候选字段名(只用于打印探查,解析仍走生产函数)。
TIME_KEYS = ("time", "publish_time", "publishTime", "publish_time_ms",
             "create_time", "createTime", "publishDate", "last_update_time",
             "publishTimeStamp", "note_publish_time")
LIKE_KEYS = ("liked_count", "like_count", "likedCount", "likes")


def _mask(obj, depth=0):
    """打印前遮蔽长 token/URL,避免把 xsec_token 刷进日志。"""
    if depth > 6:
        return "..."
    if isinstance(obj, dict):
        return {k: ("<masked>" if "token" in k.lower() else _mask(v, depth + 1))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_mask(v, depth + 1) for v in obj[:3]]
    if isinstance(obj, str) and len(obj) > 120:
        return obj[:117] + "..."
    return obj


def _pick_time_fields(node, path=""):
    """递归收集命中 TIME_KEYS 的 (路径, 原始值, dt_value解析结果)。"""
    hits = []
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{path}.{k}" if path else k
            if k in TIME_KEYS and not isinstance(v, (dict, list)):
                hits.append((p, v, dt_value(v)))
            hits += _pick_time_fields(v, p)
    elif isinstance(node, list):
        for i, v in enumerate(node[:3]):
            hits += _pick_time_fields(v, f"{path}.{i}")
    return hits


async def _get(client, path, params):
    r = await client.get(path, params=params)
    print(f"    HTTP {r.status_code}  {path}")
    r.raise_for_status()
    return r.json()


async def main():
    token = os.environ.get("TIKHUB_TOKEN", "").strip()
    if not token:
        # 便捷:直接读 backend/.env 的 TIKHUB_TOKEN(不 source 整个文件,避免 JSON 字段报错)。
        env_file = Path(__file__).resolve().parent.parent / ".env"
        if env_file.is_file():
            for line in env_file.read_text().splitlines():
                if line.startswith("TIKHUB_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not token:
        sys.exit("请先 export TIKHUB_TOKEN=...(脚本只读,不会写库)")
    keyword = sys.argv[1] if len(sys.argv) > 1 else "副业"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30,
                                 headers=headers) as client:
        # ---- 1) search:一天内 vs 一周内,看 time_filter 是否生效 + 卡片有无精确时间
        first_note = None
        for tf in ("一天内", "一周内"):
            print(f"\n=== search_notes  time_filter={tf!r}  keyword={keyword!r} ===")
            payload = await _get(client, SEARCH_PATH, {
                "keyword": keyword, "page": 1, "sort_type": "general",
                "note_type": "不限", "time_filter": tf,
                "source": "explore_feed", "ai_mode": 0,
            })
            items = unwrap_items(payload)
            print(f"    解析出 {len(items)} 条卡片")
            for i, raw in enumerate(items[:5], 1):
                hits = _pick_time_fields(raw)
                env = raw.get("note") if isinstance(raw.get("note"), dict) else raw
                like = first(env, "interact_info.liked_count",
                             "note_card.interact_info.liked_count", "liked_count")
                print(f"    [{i}] 时间字段命中: " +
                      (", ".join(f"{p}={v!r}→{d}" for p, v, d in hits) or "无")
                      + f"  | liked_count={like!r}")
                # 生产 normalize_candidate 视角
                cand = normalize_candidate(raw, "tikhub", i)
                rel = search_publish_time(raw)
                print(f"        normalize_candidate.published_at="
                      f"{cand.published_at if cand else None}  "
                      f"search_publish_time(相对标签)={rel}  like="
                      f"{cand.like_count if cand else None}")
            if first_note is None and items:
                first_note = items[0]

        # ---- 2) detail:对搜到的第一篇,两个端点都试,看谁能给精确时间戳
        if first_note:
            env = (first_note.get("note")
                   if isinstance(first_note.get("note"), dict) else first_note)
            note_id = first(env, "note_id", "id", "noteId",
                            "note_card.note_id", "note_card.id")
            xsec = first(env, "xsec_token", "xsecToken") or first(
                first_note, "xsec_token", "xsecToken")
            print(f"\n=== detail  note_id={note_id} ===")
            for label, path in (("web_v3", DETAIL_PATH_WEB_V3),
                                ("app_v2", DETAIL_PATH_APP_V2)):
                try:
                    payload = await _get(client, path,
                                         {"note_id": note_id, "xsec_token": xsec})
                except Exception as e:  # noqa: BLE001
                    print(f"    [{label}] 调用失败: {type(e).__name__}: {e}")
                    continue
                data = payload.get("data", payload) if isinstance(payload, dict) else payload
                hits = _pick_time_fields(data)
                print(f"    [{label}] 时间字段命中: " +
                      (", ".join(f"{p}={v!r}→{d}" for p, v, d in hits) or "无"))
                cand = normalize_candidate(
                    {**(data if isinstance(data, dict) else {}), "note_id": note_id},
                    "tikhub", 99)
                print(f"        normalize_candidate.published_at="
                      f"{cand.published_at if cand else None}  like="
                      f"{cand.like_count if cand else None}")

    print("\n=== 判定 ===")
    print("若 search 卡片无精确时间戳、但 detail 有 → 24h 档需先 detail 兜底才能分档;")
    print("若 search 卡片就有可用时间戳 → 24h 档可直接交给 TikHub search。")


if __name__ == "__main__":
    asyncio.run(main())

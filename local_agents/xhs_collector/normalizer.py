from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode


def first(data: Any, *paths: str):
    for path in paths:
        value = data
        for part in path.split("."):
            if isinstance(value, dict): value = value.get(part)
            elif isinstance(value, list) and part.isdigit(): value = value[int(part)] if int(part) < len(value) else None
            else: value = None; break
        if value not in (None, ""): return value
    return None


def count_value(value: Any) -> int | None:
    if value in (None, ""): return None
    text = str(value).strip().lower().replace(",", "").replace("+", "")
    try:
        if text.endswith(("万", "w")): return int(float(text[:-1]) * 10000)
        if text.endswith("k"): return int(float(text[:-1]) * 1000)
        return int(float(text))
    except ValueError: return None


def dt_value(value: Any) -> datetime | None:
    if value in (None, ""): return None
    if isinstance(value, (int, float)):
        stamp = value / 1000 if value > 10_000_000_000 else value
        try: return datetime.fromtimestamp(stamp)
        except (ValueError, OSError): return None
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError: return None


def search_time(raw: dict[str, Any]) -> datetime | None:
    now = datetime.now()
    tags = first(raw, "corner_tag_info", "note_card.corner_tag_info") or []
    text = next((str(item.get("text") or "") for item in tags if isinstance(item, dict) and item.get("type") == "publish_time"), "")
    if text in {"刚刚", "今天"} or "分钟前" in text or "小时前" in text: return now
    if text.startswith("昨天"): return now - timedelta(days=1)
    days = re.search(r"(\d+)\s*天前", text)
    if days: return now - timedelta(days=int(days.group(1)))
    short = re.search(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})(?!\d)", text)
    if short:
        try:
            result = datetime(now.year, int(short.group(1)), int(short.group(2)))
            return result.replace(year=now.year - 1) if result > now + timedelta(days=1) else result
        except ValueError: pass
    return None


def unwrap(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list): return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict): return []
    data = payload.get("data", payload)
    if isinstance(data, list): return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("items", "notes", "feeds", "note_list", "list"):
            if isinstance(data.get(key), list): return [x for x in data[key] if isinstance(x, dict)]
        if "data" in data: return unwrap(data["data"])
    return []


def has_result_list(payload: Any) -> bool:
    """Whether the CLI response contains a recognized result-list field, including an empty list."""
    if isinstance(payload, list): return True
    if not isinstance(payload, dict): return False
    data = payload.get("data", payload)
    if isinstance(data, list): return True
    if isinstance(data, dict):
        if any(isinstance(data.get(key), list) for key in ("items", "notes", "feeds", "note_list", "list")): return True
        if "data" in data: return has_result_list(data["data"])
    return False


def find_note(value: Any, depth: int = 0) -> dict[str, Any] | None:
    if depth > 5: return None
    if isinstance(value, dict):
        if first(value, "note_id", "noteId") or (value.get("id") and any(key in value for key in ("title", "display_title", "desc", "interact_info"))): return value
        for key in ("note", "note_card", "note_info", "data", "item", "items", "feeds"):
            found = find_note(value.get(key), depth + 1)
            if found: return found
    elif isinstance(value, list):
        for item in value:
            found = find_note(item, depth + 1)
            if found: return found
    return None


def normalize(raw: dict[str, Any], provider_rank: int = 1) -> dict[str, Any] | None:
    if raw.get("model_type") not in (None, "", "note"): return None
    note = raw.get("note") if isinstance(raw.get("note"), dict) else find_note(raw) or raw
    note_id = first(note, "note_id", "id", "noteId", "note_card.note_id", "note_card.id")
    if not note_id: return None
    user = first(note, "user", "author", "note_card.user") or {}
    interact = first(note, "interact_info", "interactInfo", "note_card.interact_info") or {}
    note_type = str(first(note, "type", "note_type", "note_card.type") or "").lower()
    note_type = "video" if "video" in note_type else "image" if note_type else None
    cover = first(note, "cover.url_default", "cover.url", "cover_url", "image_list.0.url_default", "note_card.cover.url_default")
    url = first(note, "url", "share_url", "note_url")
    if not url:
        url = f"https://www.xiaohongshu.com/explore/{note_id}"
        token = first(raw, "xsec_token", "note_card.xsec_token")
        if token: url += "?" + urlencode({"xsec_token": str(token), "xsec_source": "pc_search"})
    metric = lambda *keys: count_value(first(interact, *keys) if first(interact, *keys) is not None else first(note, *keys))
    return {
        "note_id": str(note_id),
        "title": str(first(note, "title", "display_title", "note_card.display_title") or ""),
        "content": str(first(note, "desc", "content", "note_card.desc") or ""),
        "published_at": (dt_value(first(note, "published_at", "time", "publish_time", "note_card.time")) or search_time(raw)),
        "note_type": note_type,
        "author": {"id": first(user, "user_id", "id", "userid"), "nickname": first(user, "nickname", "nick_name", "name") or "", "bio": first(user, "desc", "bio") or "", "avatar_url": first(user, "avatar", "image")},
        "cover_url": cover,
        "engagement": {"likes": metric("liked_count", "like_count", "likedCount", "likes"), "collects": metric("collected_count", "collect_count", "collectedCount", "collects"), "comments": metric("comment_count", "commentCount", "comments"), "shares": metric("share_count", "shared_count", "shareCount", "shares"), "views": metric("view_count", "viewCount", "views")},
        "tags": [str(x.get("name") if isinstance(x, dict) else x) for x in (first(note, "tag_list", "tags") or []) if x],
        "original_url": str(url),
        "provider_rank": provider_rank,
    }


def merge(search_item: dict[str, Any], detail_item: dict[str, Any] | None) -> dict[str, Any]:
    if not detail_item: return search_item
    merged = dict(search_item)
    for key in ("title", "content", "published_at", "note_type", "cover_url", "original_url"):
        if detail_item.get(key) not in (None, ""): merged[key] = detail_item[key]
    merged["author"] = {**(search_item.get("author") or {}), **{k: v for k, v in (detail_item.get("author") or {}).items() if v not in (None, "")}}
    merged["engagement"] = {**(search_item.get("engagement") or {}), **{k: v for k, v in (detail_item.get("engagement") or {}).items() if v is not None}}
    merged["tags"] = list(dict.fromkeys((search_item.get("tags") or []) + (detail_item.get("tags") or [])))
    return merged

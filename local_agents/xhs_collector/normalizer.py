from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse


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


def xsec_token(url: Any) -> str:
    if not url: return ""
    return (parse_qs(urlparse(str(url)).query).get("xsec_token") or [""])[0]


def xsec_note_url(note_id: str, url: Any = None, token: Any = None, source: Any = None) -> str:
    """将搜索结果中分开返回的 token 合并到可直达的笔记 URL。"""
    raw_url = str(url or "").strip()
    query = parse_qs(urlparse(raw_url).query) if raw_url else {}
    resolved_token = str(token or (query.get("xsec_token") or [""])[0]).strip()
    resolved_source = str(source or (query.get("xsec_source") or [""])[0] or "pc_search").strip()
    stable_url = f"https://www.xiaohongshu.com/explore/{note_id}"
    if not resolved_token: return raw_url or stable_url
    return stable_url + "?" + urlencode({"xsec_token": resolved_token, "xsec_source": resolved_source})


def remote_image_url(value: Any) -> str | None:
    if not value:
        return None
    url = str(value).strip()
    if url.startswith("http://") and ".xhscdn.com/" in url:
        return "https://" + url[len("http://"):]
    return url


def normalize(raw: dict[str, Any], provider_rank: int = 1) -> dict[str, Any] | None:
    if raw.get("model_type") not in (None, "", "note"): return None
    note = raw.get("note") if isinstance(raw.get("note"), dict) else find_note(raw) or raw
    note_id = first(note, "note_id", "id", "noteId", "note_card.note_id", "note_card.id")
    if not note_id: return None
    user = first(note, "user", "author", "note_card.user") or {}
    interact = first(note, "interact_info", "interactInfo", "note_card.interact_info") or {}
    note_type = str(first(note, "type", "note_type", "note_card.type") or "").lower()
    note_type = "video" if "video" in note_type else "image" if note_type else None
    cover = remote_image_url(first(note, "cover.url_default", "cover.url", "cover_url", "image_list.0.url_default", "note_card.cover.url_default"))
    raw_url = first(note, "url", "share_url", "note_url") or first(raw, "url", "share_url", "note_url")
    token = first(note, "xsec_token", "xsecToken") or first(raw, "xsec_token", "xsecToken", "note_card.xsec_token", "note_card.xsecToken")
    source = first(note, "xsec_source", "xsecSource") or first(raw, "xsec_source", "xsecSource", "note_card.xsec_source", "note_card.xsecSource")
    url = xsec_note_url(str(note_id), raw_url, token, source)
    metric = lambda *keys: count_value(first(interact, *keys) if first(interact, *keys) is not None else first(note, *keys))
    return {
        "note_id": str(note_id),
        "title": str(first(note, "title", "display_title", "note_card.display_title") or ""),
        "content": str(first(note, "desc", "content", "note_card.desc") or ""),
        "published_at": (dt_value(first(note, "published_at", "time", "publish_time", "note_card.time")) or search_time(raw)),
        "note_type": note_type,
        "author": {"id": first(user, "user_id", "id", "userid"), "nickname": first(user, "nickname", "nick_name", "name") or "", "bio": first(user, "desc", "bio") or "", "avatar_url": remote_image_url(first(user, "avatar", "image"))},
        "cover_url": cover,
        "engagement": {"likes": metric("liked_count", "like_count", "likedCount", "likes"), "collects": metric("collected_count", "collect_count", "collectedCount", "collects"), "comments": metric("comment_count", "commentCount", "comments"), "shares": metric("share_count", "shared_count", "shareCount", "shares"), "views": metric("view_count", "viewCount", "views")},
        "tags": [str(x.get("name") if isinstance(x, dict) else x) for x in (first(note, "tag_list", "tags") or []) if x],
        "original_url": str(url),
        "provider_rank": provider_rank,
    }


def merge(search_item: dict[str, Any], detail_item: dict[str, Any] | None) -> dict[str, Any]:
    if not detail_item: return search_item
    merged = dict(search_item)
    for key in ("title", "content", "published_at", "note_type", "cover_url"):
        if detail_item.get(key) not in (None, ""): merged[key] = detail_item[key]
    # 详情 JSON 通常只返回裸 URL，不能用它覆盖搜索卡片的 token 链接。
    search_url = search_item.get("original_url")
    detail_url = detail_item.get("original_url")
    if xsec_token(detail_url) or not search_url:
        merged["original_url"] = detail_url
    merged["author"] = {**(search_item.get("author") or {}), **{k: v for k, v in (detail_item.get("author") or {}).items() if v not in (None, "")}}
    merged["engagement"] = {**(search_item.get("engagement") or {}), **{k: v for k, v in (detail_item.get("engagement") or {}).items() if v is not None}}
    merged["tags"] = list(dict.fromkeys((search_item.get("tags") or []) + (detail_item.get("tags") or [])))
    return merged

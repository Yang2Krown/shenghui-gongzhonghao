"""博查 Bocha 搜索客户端（国内可充值，替代 Exa/搜狗）。

只用于实操类创作的爆文搜索，先小范围试水。
API 文档：https://open.bochaai.com/  端点 POST https://api.bochaai.com/v1/web-search

探针用法（填好 BOCHA_API_KEY 后）：
    python -m app.services.practical_creation.bocha 墨刀
    python -m app.services.practical_creation.bocha 墨刀 --wechat   # 限定公众号域名
"""

import logging
from typing import List, Dict, Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_API = "https://api.bochaai.com/v1/web-search"


async def bocha_search(
    query: str, count: int = 10, wechat_only: bool = False,
    freshness: str = "noLimit", include: str = "", exclude: str = "",
) -> List[Dict[str, Any]]:
    """博查 web 搜索。返回 [{title, url, snippet, summary, site, date}]。

    wechat_only=True 时限定 mp.weixin.qq.com 域名。
    freshness: 时间范围，oneDay/oneWeek/oneMonth/oneYear/noLimit（滚动窗口，随当前时间动态变化）。
    include: 限定域名白名单，多个用 | 分隔（实测有效，用来只搜优质平台）。
    exclude: 排除域名黑名单，多个用 | 分隔。
    """
    if not settings.BOCHA_API_KEY:
        raise RuntimeError("BOCHA_API_KEY 未配置")

    # 域名过滤用 body 的 include/exclude 参数（query 里写 site: 无效）
    payload = {"query": query, "count": count, "summary": True, "freshness": freshness}
    if wechat_only:
        payload["include"] = "mp.weixin.qq.com"
    elif include:
        payload["include"] = include
    if exclude:
        payload["exclude"] = exclude

    # 博查是国内 API，直连即可；trust_env=False 避免服务器上残留代理 env 把请求拖死
    async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
        resp = await client.post(
            _API,
            json=payload,
            headers={"Authorization": f"Bearer {settings.BOCHA_API_KEY}",
                     "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

    return _parse(data)


def _parse(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从博查响应里抽 web 结果，做防御式解析（字段名变了也不崩）。"""
    # 兼容 {data:{webPages:{value:[...]}}} 与可能的扁平结构
    pages = (
        (((data or {}).get("data") or {}).get("webPages") or {}).get("value")
        or (((data or {}).get("webPages") or {}).get("value"))
        or []
    )
    out = []
    for p in pages:
        out.append({
            "title": p.get("name") or p.get("title") or "",
            "url": p.get("url") or "",
            "snippet": p.get("snippet") or "",
            "summary": p.get("summary") or "",
            "site": p.get("siteName") or "",
            "date": p.get("dateLastCrawled") or p.get("datePublished") or "",
        })
    return out


# ── 探针：直接看博查搜到啥 ──
def _probe():
    import sys
    import asyncio
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    kw = args[0] if args else "墨刀"
    wechat = "--wechat" in sys.argv
    print(f"博查搜索: query={kw!r} 公众号限定={wechat}\n" + "=" * 60)
    try:
        results = asyncio.run(bocha_search(kw, count=10, wechat_only=wechat))
    except Exception as e:
        print(f"调用失败: {type(e).__name__}: {e}")
        return
    print(f"返回 {len(results)} 条：\n")
    for i, r in enumerate(results, 1):
        print(f"[{i}] {r['title']}")
        print(f"    url : {r['url']}")
        print(f"    site: {r['site']}  date: {r['date']}")
        body = r["summary"] or r["snippet"]
        print(f"    摘要: {body[:160]}")
        print()


if __name__ == "__main__":
    _probe()

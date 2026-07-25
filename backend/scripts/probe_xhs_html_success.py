"""成功率实测:用库内真实笔记链接跑 HTML 免费抓取,统计当前网络环境下的成功率。

用法:
    cd backend && .venv/bin/python scripts/probe_xhs_html_success.py --limit 30
    .venv/bin/python scripts/probe_xhs_html_success.py --url-file urls.txt --verbose

数据源(二选一):
    默认从 XhsNote 表取最近 --limit 条 latest_xsec_url 非空的笔记(只读,不写库);
    --url-file 改为从文本文件逐行读链接(空行与 # 开头行忽略),完全不连库。

逐条串行调用 extract_xhs,条间随机 sleep 2~5 秒,低频不触发风控。每条按
complete(六项齐全)/ partial(有正文但缺字段)/ blocked(风控)/ failed(失败)
归档并打印一行,结尾输出各类占比与图文/视频分项成功率。

注意:会真实请求小红书网页,仅供低频人工实测,勿挂定时任务。
"""
from __future__ import annotations

import argparse
import asyncio
import random
import sys
from collections import Counter
from pathlib import Path

# 允许在 backend/ 下以脚本路径直接运行:把包根加进 sys.path。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.xhs import XhsNote  # noqa: E402
from app.services.scraping.link_extractor import extract_xhs  # noqa: E402

# complete 判定:这六项齐全才算完整
REQUIRED_FIELDS = ("title", "content", "author",
                   "cover_url", "published_at", "like_count")
# extract_xhs 失败时 content 的前缀(见 link_extractor 的异常分支)
FAILED_PREFIXES = ("提取失败", "请求失败")


def classify(result: dict) -> tuple[str, list[str]]:
    """归档为 complete/partial/blocked/failed;partial 时附带缺失字段名。"""
    if result.get("blocked"):
        return "blocked", []
    content = (result.get("content") or "").strip()
    if not content or content.startswith(FAILED_PREFIXES):
        return "failed", []
    missing = [f for f in REQUIRED_FIELDS if result.get(f) in (None, "", [])]
    return ("partial", missing) if missing else ("complete", [])


def _short_url(url: str) -> str:
    """打印用:去掉 query,避免把 xsec_token 刷进日志。"""
    return url.split("?", 1)[0]


def load_items_from_db(limit: int) -> list[tuple[str, str | None]]:
    """只读查询:最近 limit 条 latest_xsec_url 非空的笔记,返回 (url, note_type)。"""
    stmt = (
        select(XhsNote.latest_xsec_url, XhsNote.note_type)
        .where(XhsNote.latest_xsec_url.isnot(None),
               XhsNote.latest_xsec_url != "")
        .order_by(XhsNote.last_discovered_at.desc())
        .limit(limit)
    )
    with SessionLocal() as db:
        return [(u, nt) for u, nt in db.execute(stmt).all() if u]


def load_items_from_file(path: str, limit: int) -> list[tuple[str, str | None]]:
    """从文本文件逐行读链接(空行与 # 注释忽略),不连数据库。"""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    urls = [ln.strip() for ln in lines
            if ln.strip() and not ln.lstrip().startswith("#")]
    return [(u, None) for u in urls[:limit]]


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="用真实笔记链接实测小红书 HTML 免费抓取成功率(只读)。")
    parser.add_argument("--limit", type=int, default=20,
                        help="取样条数,默认 20")
    parser.add_argument("--url-file",
                        help="改为从该文本文件逐行读链接,不查数据库")
    parser.add_argument("--verbose", action="store_true",
                        help="打印每条的正文长度、各字段值等细节")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit 必须 >= 1")

    items = (load_items_from_file(args.url_file, args.limit)
             if args.url_file else load_items_from_db(args.limit))
    if not items:
        sys.exit("没有可用样本(latest_xsec_url 为空或文件无链接)")

    cookie = settings.XHS_WEB_COOKIE or None
    source = f"url-file {args.url_file}" if args.url_file else "XhsNote 表"
    print(f"样本: {len(items)} 条(来源 {source})  "
          f"cookie: {'已配置' if cookie else '未配置'}")

    stats: Counter[str] = Counter()
    missing_counter: Counter[str] = Counter()
    by_type: dict[str, list[int]] = {}  # note_type -> [成功数, 总数]

    for i, (url, db_note_type) in enumerate(items, 1):
        try:
            result = await extract_xhs(url, cookie=cookie)
            kind, missing = classify(result)
            note_id = result.get("note_id") or _short_url(url)
            note_type = result.get("note_type") or db_note_type or "unknown"
        except Exception as e:  # noqa: BLE001 - 契约是不抛异常,这里仅兜底防御
            kind, missing = "failed", []
            note_type = db_note_type or "unknown"
            print(f"[{i:>2}/{len(items)}] {kind:<8}  {_short_url(url)}  "
                  f"异常: {type(e).__name__}: {e}")
        else:
            content_len = len((result.get("content") or "").strip())
            if kind == "partial":
                tail = f"缺: {','.join(missing)}"
            elif kind == "complete":
                tail = f"正文: {content_len}字"
            else:
                tail = ""
            print(f"[{i:>2}/{len(items)}] {kind:<8}  {note_id}  {tail}")
            if args.verbose:
                print(f"      url={_short_url(url)}")
                print(f"      title={result.get('title')!r} "
                      f"author={result.get('author')!r} "
                      f"type={note_type} like={result.get('like_count')} "
                      f"published_at={result.get('published_at')!r} "
                      f"tags={len(result.get('tags') or [])} "
                      f"cover={'有' if result.get('cover_url') else '无'} "
                      f"正文={content_len}字")

        stats[kind] += 1
        missing_counter.update(missing)
        slot = by_type.setdefault(note_type, [0, 0])
        slot[1] += 1
        if kind in ("complete", "partial"):
            slot[0] += 1
        if i < len(items):
            await asyncio.sleep(random.uniform(2, 5))

    total = len(items)
    success = stats["complete"] + stats["partial"]
    print("\n=== 汇总 ===")
    print(f"总数: {total}")
    for kind in ("complete", "partial", "blocked", "failed"):
        print(f"{kind:<9}: {stats[kind]:>2}  ({stats[kind] / total:.1%})")
    if missing_counter:
        common = ", ".join(f"{k}×{v}" for k, v in missing_counter.most_common())
        print(f"partial 常见缺失: {common}")
    print(f"成功率(complete+partial): {success}/{total} = {success / total:.1%}")
    if any(t != "unknown" for t in by_type):
        print("分项成功率(complete+partial):")
        for note_type, (ok, n) in sorted(by_type.items()):
            print(f"  {note_type:<8}: {ok}/{n} ({ok / n:.1%})")


if __name__ == "__main__":
    asyncio.run(main())

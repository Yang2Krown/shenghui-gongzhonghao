"""种子脚本：从课程网页版.html 导入 12 章内容到 course_chapters 表。

在本地执行（backend 目录下）：
    cd /Users/yang2krown/工作/公众号智能体/gzh/backend
    python -m scripts.seed_course_chapters

或直接运行：
    python scripts/seed_course_chapters.py
"""

import asyncio
import os
import re
import sys
from pathlib import Path

# ── 路径修正，确保能导入 backend 模块 ──────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# HTML 文件路径：尝试多个位置（本地开发 + 服务器）
_CANDIDATES = [
    Path("/Users/yang2krown/工作/公众号智能体/课程网页版.html"),  # 本地 Mac
    Path("/www/wwwroot/gzh/课程网页版.html"),                     # 服务器项目根目录
    Path(__file__).resolve().parent.parent.parent / "课程网页版.html",  # 相对路径兜底
]
HTML_FILE = next((p for p in _CANDIDATES if p.exists()), None)


# ── HTML 解析 ──────────────────────────────────────────────────

def _extract_nav_names(html: str) -> dict[int, str]:
    """从侧边栏 nav items 提取每章的短名称（如"认知篇"、"定位篇"）。"""
    pattern = re.compile(
        r'data-go="(\d+)"[^>]*>.*?<span class="nav-name">(.*?)</span>',
        re.DOTALL,
    )
    result = {}
    for m in pattern.finditer(html):
        idx = int(m.group(1))
        name = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        result[idx] = name
    return result


def _extract_chapters(html: str) -> list[dict]:
    """从 HTML 提取每个章节的 kicker / title / content_html。"""
    chapters = []

    # 按 <section class="chapter" 分割
    section_pattern = re.compile(
        r'<section class="chapter" id="ch(\d+)"[^>]*>(.*?)</section>',
        re.DOTALL,
    )

    for m in section_pattern.finditer(html):
        idx = int(m.group(1))
        section_html = m.group(2)

        # 提取 kicker
        kicker_m = re.search(
            r'<div class="ch-kicker">(.*?)</div>', section_html, re.DOTALL
        )
        kicker = kicker_m.group(1).strip() if kicker_m else ""

        # 提取 title (h1)
        title_m = re.search(r"<h1>(.*?)</h1>", section_html, re.DOTALL)
        title = title_m.group(1).strip() if title_m else ""

        # 提取 prose 内容（从 <div class="prose"> 到 <div class="pager">）
        prose_start = section_html.find('<div class="prose">')
        pager_start = section_html.find('<div class="pager">')
        if prose_start != -1 and pager_start != -1:
            # 跳过 <div class="prose"> 标签本身
            content_start = prose_start + len('<div class="prose">')
            content_html = section_html[content_start:pager_start].strip()
            # 去掉末尾多余的 </div>（prose 的闭合标签）
            content_html = content_html.rstrip()
            if content_html.endswith("</div>"):
                content_html = content_html[:-6].strip()
        else:
            content_html = ""

        chapters.append({
            "sort_order": idx,
            "kicker": kicker,
            "title": title,
            "content_html": content_html,
        })

    return chapters


# ── 数据库写入 ─────────────────────────────────────────────────

async def seed():
    """读取 HTML、解析章节、写入数据库。"""
    from app.db.session import AsyncSessionLocal
    from app.models.course import CourseChapter
    from sqlalchemy import select, func

    if not HTML_FILE:
        print("❌ 找不到课程网页版.html，请把文件放到项目根目录")
        return

    html = HTML_FILE.read_text(encoding="utf-8")
    nav_names = _extract_nav_names(html)
    chapters = _extract_chapters(html)

    if not chapters:
        print("❌ 未从 HTML 中提取到任何章节")
        return

    print(f"📖 从 HTML 提取到 {len(chapters)} 个章节")

    async with AsyncSessionLocal() as db:
        # 检查是否已有数据
        count = (await db.execute(select(func.count(CourseChapter.id)))).scalar()
        if count and count > 0:
            print(f"⚠️  表中已有 {count} 条记录，跳过导入。如需重新导入请先清空表。")
            return

        for ch in chapters:
            subtitle = nav_names.get(ch["sort_order"], "")
            record = CourseChapter(
                title=ch["title"],
                subtitle=subtitle,
                kicker=ch["kicker"],
                content_html=ch["content_html"],
                sort_order=ch["sort_order"],
                is_published=True,
            )
            db.add(record)
            print(f"  ✅ [{ch['sort_order']:02d}] {ch['kicker']} | {ch['title'][:40]}... | 副标题: {subtitle}")

        await db.commit()
        print(f"\n🎉 成功导入 {len(chapters)} 个章节到 course_chapters 表")


if __name__ == "__main__":
    asyncio.run(seed())

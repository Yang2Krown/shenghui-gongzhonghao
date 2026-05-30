"""一次性源调整（2026-05，国内服务器·无代理）：

1. 禁用所有"会被墙"的源（Google News 路由 / Google 系 / Reddit / 被墙欧美媒体官博 等）。
   —— 唯一例外：rss「OpenAI Blog」按用户要求保留（用户自行解决访问）。
2. 新增一批国内可直连的科技 / AI RSS 源。

幂等：可重复执行。运行：
    python -m app.db.seeds.seed_source_changes_2026
"""

import asyncio
import logging
import re

from sqlalchemy import select, or_, and_

from app.db.session import AsyncSessionLocal
from app.models.source_registry import SourceRegistry, SOURCE_TYPE_RSS, SOURCE_TYPE_REDDIT

logger = logging.getLogger(__name__)


# ── 新增 RSS 源（国内可直连）。(name, url, 分类) ──
NEW_RSS = [
    ("TechCrunch", "https://techcrunch.com/feed/", "综合科技"),
    ("The Verge", "https://www.theverge.com/rss/index.xml", "综合科技"),
    ("Engadget", "https://www.engadget.com/rss.xml", "综合科技"),
    ("VentureBeat", "https://venturebeat.com/feed/", "综合科技"),
    ("Ars Technica - AI", "https://arstechnica.com/ai/feed/", "AI"),
    ("Ars Technica - Gadgets", "https://arstechnica.com/gadgets/feed/", "综合科技"),
    ("Ars Technica - IT", "https://arstechnica.com/information-technology/feed/", "综合科技"),
    ("36氪", "https://36kr.com/feed", "综合科技"),
    ("钛媒体", "https://www.tmtpost.com/rss.xml", "综合科技"),
    ("InfoQ中国", "https://www.infoq.cn/feed", "综合科技"),
    ("MIT Technology Review AI", "https://www.technologyreview.com/topic/artificial-intelligence/feed", "AI"),
    ("OpenAI Blog", "https://openai.com/blog/rss.xml", "AI"),
    ("Wired", "https://www.wired.com/feed/rss", "综合科技"),
    ("Techmeme", "https://www.techmeme.com/feed.xml", "综合科技"),
    ("SCMP Tech", "https://www.scmp.com/rss/36/feed", "综合科技"),
    ("SCMP Business", "https://www.scmp.com/rss/92/feed", "综合科技"),
    # ── AI 专向 feed（2026-05 实测可解析、国内可直连）──
    ("The Decoder", "https://the-decoder.com/feed/", "AI"),
    ("MarkTechPost", "https://www.marktechpost.com/feed/", "AI"),
    ("AI News", "https://www.artificialintelligence-news.com/feed/", "AI"),
    ("NVIDIA Blog", "https://blogs.nvidia.com/feed/", "AI"),
    ("Synced 机器之心Global", "https://syncedreview.com/feed/", "AI"),
    ("The Gradient", "https://thegradient.pub/rss/", "AI"),
    ("Machine Learning Mastery", "https://machinelearningmastery.com/feed/", "AI"),
    ("Berkeley AI Research", "https://bair.berkeley.edu/blog/feed.xml", "AI"),
    ("ZDNet AI", "https://www.zdnet.com/topic/artificial-intelligence/rss.xml", "AI"),
    ("SiliconANGLE AI", "https://siliconangle.com/category/ai/feed/", "AI"),
]

# ── 被墙域名（国内无代理直连不通）。命中 url 的源一律禁用 ──
# 注意：故意不含 openai.com —— rss「OpenAI Blog」要保留。
BLOCKED_URL_PATTERNS = [
    "news.google.com",   # Google News（整站被墙），大量中文源走它路由
    "blog.google",       # Google 官博
    "huggingface.co",
    "bloomberg.com",
    "economist.com",
    "www.ft.com",        # Financial Times
    "ft.com/rss",
]

# web 类被墙官博（按域名禁用，scoped 在 source_type='web' 上，不会误伤 rss OpenAI Blog）
BLOCKED_WEB_URL_PATTERNS = ["anthropic.com", "deepmind.google", "openai.com"]

# 微信公众号(sogou) 搜索关键词：按 AI 主题搜，不再用博主名
SOGOU_KEYWORDS = [
    "大模型", "AI Agent", "Coding Agent", "Claude", "ChatGPT", "DeepSeek",
    "Cursor", "AI 编程", "vibe coding", "Sora", "AI 视频", "可灵", "即梦",
    "Midjourney", "AI 绘画", "文生图", "提示词", "MCP", "智能体", "AI 工作流",
    "多模态", "AI 应用", "开源模型", "具身智能",
]


def _slug_platform(name: str) -> str:
    s = re.sub(r"[\s/\\()（）【】\.,，。、]+", "_", name).strip("_")[:60]
    return f"rss_{s}"


async def _upsert_rss(db, *, name: str, url: str, direction: str) -> str:
    platform = _slug_platform(name)
    existing = (await db.execute(
        select(SourceRegistry).where(SourceRegistry.platform == platform)
    )).scalar_one_or_none()
    if existing:
        existing.name = name
        existing.url = url
        existing.source_type = SOURCE_TYPE_RSS
        existing.direction_tags = list({*(existing.direction_tags or []), direction})
        existing.weight = 5            # 所有来源平等
        existing.enabled = True
        return "updated"
    db.add(SourceRegistry(
        name=name,
        platform=platform,
        source_type=SOURCE_TYPE_RSS,
        url=url,
        tier=None,
        direction_tags=[direction],
        weight=5,
        requires_auth=False,
        auth_status="ok",
        fetch_strategy="cron",
        fetch_config={},
        enabled=True,
        description=f"RSS 源（{direction}）",
    ))
    return "created"


async def run(db) -> dict:
    stats = {"rss_created": 0, "rss_updated": 0, "disabled": 0}

    # 1. 新增 / 更新 RSS（先做，确保不会被下面的禁用误伤）
    for name, url, direction in NEW_RSS:
        outcome = await _upsert_rss(db, name=name, url=url, direction=direction)
        stats["rss_created" if outcome == "created" else "rss_updated"] += 1

    # 2. 禁用被墙源
    url_conds = [SourceRegistry.url.ilike(f"%{p}%") for p in BLOCKED_URL_PATTERNS]
    web_conds = [SourceRegistry.url.ilike(f"%{p}%") for p in BLOCKED_WEB_URL_PATTERNS]
    blocked = (await db.execute(
        select(SourceRegistry).where(
            SourceRegistry.enabled.is_(True),
            or_(
                or_(*url_conds),
                SourceRegistry.source_type == SOURCE_TYPE_REDDIT,
                and_(SourceRegistry.source_type == "web", or_(*web_conds)),
            ),
        )
    )).scalars().all()

    disabled_names = []
    for s in blocked:
        s.enabled = False
        disabled_names.append(f"{s.source_type}:{s.name}")
        stats["disabled"] += 1

    # 3. 微信公众号(sogou)源：改名 + 写入主题关键词（不再用博主名搜）
    renamed = 0
    sogou_sources = (await db.execute(
        select(SourceRegistry).where(SourceRegistry.source_type == "sogou_wechat")
    )).scalars().all()
    for s in sogou_sources:
        if s.name != "微信公众号":
            s.name = "微信公众号"
            renamed += 1
        cfg = dict(s.fetch_config or {})
        cfg["keywords"] = SOGOU_KEYWORDS
        cfg["max_keywords"] = len(SOGOU_KEYWORDS)
        cfg["limit_per_keyword"] = 10
        s.fetch_config = cfg
    stats["renamed"] = renamed
    stats["sogou_keywords"] = len(SOGOU_KEYWORDS)

    # 4. 小红书源收窄到"数码科技"分类（美妆/家装/学习等生活类对 AI 话题库无用，全被过滤）
    xhs_narrowed = 0
    xhs_sources = (await db.execute(
        select(SourceRegistry).where(SourceRegistry.source_type == "xhs_daily")
    )).scalars().all()
    for s in xhs_sources:
        cfg = dict(s.fetch_config or {})
        if cfg.get("categories") != ["数码科技"]:
            cfg["categories"] = ["数码科技"]
            s.fetch_config = cfg
            xhs_narrowed += 1
    stats["xhs_narrowed"] = xhs_narrowed

    await db.commit()
    logger.info(f"seed_source_changes_2026: {stats}")
    if disabled_names:
        logger.info("已禁用：\n  - " + "\n  - ".join(sorted(disabled_names)))
    return {**stats, "disabled_list": sorted(disabled_names)}


async def _main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    async with AsyncSessionLocal() as db:
        result = await run(db)
    print("=" * 60)
    print(f"  新增 RSS : created={result['rss_created']} updated={result['rss_updated']}")
    print(f"  改名     : 搜狗微信搜索 → 微信公众号 ({result.get('renamed', 0)} 个)")
    print(f"  公众号词 : 写入 {result.get('sogou_keywords', 0)} 个主题关键词")
    print(f"  小红书   : 收窄到「数码科技」分类 ({result.get('xhs_narrowed', 0)} 个源)")
    print(f"  已禁用   : {result['disabled']} 个")
    for n in result["disabled_list"]:
        print(f"    - {n}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(_main())

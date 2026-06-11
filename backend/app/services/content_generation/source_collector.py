"""事实素材搜集器（Phase 0）。

职责：
1. 根据 cluster_id 查询簇内所有 RawInfo（原始报道）
2. 对每篇文章，用 LLM 提取与大纲相关的关键事实
3. 合并去重，生成按大纲节组织的「事实素材包」

设计原则：
- 每篇文章单独提取，避免 context 溢出
- 用 DeepSeek（便宜）做提取，不用贵的模型
- 提取结果按大纲节组织，写作 Agent 直接可用
"""

import asyncio
import logging
from typing import List, Optional
from dataclasses import dataclass, field

from app.services.llm.llm_client import ChatMessage, parse_json_loose

logger = logging.getLogger(__name__)


@dataclass
class ExtractedFact:
    """单条提取的事实。"""
    text: str                           # 事实描述
    section_hint: int = 0               # 关联的大纲节号（0=不确定）
    source_title: str = ""              # 来源文章标题
    source_url: str = ""                # 来源 URL
    source_date: str = ""               # 来源发布日期


@dataclass
class ArticleFacts:
    """单篇文章提取的事实集合。"""
    article_id: int
    title: str
    url: str
    published_at: str
    facts: List[ExtractedFact] = field(default_factory=list)


@dataclass
class SourceMaterial:
    """最终的事实素材包。"""
    article_count: int                  # 素材来源文章数
    total_facts: int                    # 事实总条数
    facts_by_section: dict = field(default_factory=dict)  # {节号: [fact_text, ...]}
    raw_articles: List[ArticleFacts] = field(default_factory=list)  # 原始提取结果

    def to_prompt_text(self, sections: list) -> str:
        """格式化为 Agent A 可用的提示词文本。

        Args:
            sections: 大纲节列表，每个元素需有 section_number 和 subtitle
        """
        lines = []
        lines.append(f"【事实素材】（来自 {self.article_count} 篇原始报道，共 {self.total_facts} 条关键事实）")
        lines.append("")

        # 按大纲节组织
        for sec in sections:
            sec_num = sec.section_number if hasattr(sec, 'section_number') else sec.get('section_number', 0)
            subtitle = sec.subtitle if hasattr(sec, 'subtitle') else sec.get('subtitle', '')
            facts = self.facts_by_section.get(sec_num, [])
            if facts:
                lines.append(f"--- 关于「{subtitle}」的事实 ---")
                for f in facts:
                    lines.append(f"  · {f}")
                lines.append("")

        # 未归类的事实
        uncategorized = self.facts_by_section.get(0, [])
        if uncategorized:
            lines.append("--- 跨节通用事实 ---")
            for f in uncategorized:
                lines.append(f"  · {f}")
            lines.append("")

        # 来源列表
        lines.append("--- 素材来源 ---")
        for af in self.raw_articles:
            date_str = f"（{af.published_at}）" if af.published_at else ""
            lines.append(f"  · {af.title}{date_str}")
        lines.append("")

        lines.append("【使用规则】")
        lines.append("- 正文中涉及的具体事实（数字、日期、人名、产品名、版本号、价格、事件）只能来自以上素材")
        lines.append("- 素材中没有的信息，用泛化表述（据报道、业内人士透露），不要编造具体数据")
        lines.append("- 如果素材不足以支撑某个论点，直接跳过或改用不依赖具体事实的分析性表述")

        return "\n".join(lines)


def _build_extraction_prompt(article_title: str, article_content: str, outline_subtitles: List[str]) -> str:
    """构建单篇文章的事实提取提示词。"""
    lines = []
    lines.append("你是一位事实提取专家。请从以下文章中提取与给定大纲相关的关键事实。")
    lines.append("")
    lines.append("【大纲小标题】")
    for i, title in enumerate(outline_subtitles, 1):
        lines.append(f"  第{i}节: {title}")
    lines.append("")
    lines.append("【原文】")
    lines.append(f"标题: {article_title}")
    lines.append(article_content[:8000])  # 防止单篇超长
    lines.append("")
    lines.append("【提取要求】")
    lines.append("1. 提取具体事实：数字、日期、人名、产品名、版本号、价格、机构名、事件")
    lines.append("2. 不提取观点、评论、分析、比喻")
    lines.append("3. 每条事实保持原文措辞，不要改写")
    lines.append("4. 如果某节在原文中没有相关信息，输出空数组")
    lines.append("5. 不确定属于哪节的事实，section 设为 0")
    lines.append("")
    lines.append("【输出格式】严格 JSON：")
    lines.append("""```json
{
  "facts": [
    {"text": "事实描述", "section": 1},
    {"text": "另一个事实", "section": 2}
  ]
}
```""")
    return "\n".join(lines)


async def _extract_facts_from_article(
    article_id: int,
    title: str,
    content: str,
    url: str,
    published_at: str,
    outline_subtitles: List[str],
    client,
) -> ArticleFacts:
    """从单篇文章中提取事实。"""
    result = ArticleFacts(
        article_id=article_id,
        title=title,
        url=url,
        published_at=published_at or "",
    )

    if not content or len(content.strip()) < 50:
        logger.warning(f"[事实提取] 文章 {article_id} 内容过短，跳过")
        return result

    prompt = _build_extraction_prompt(title, content, outline_subtitles)
    messages = [
        ChatMessage(role="system", content="你是事实提取专家。只输出 JSON，不要解释。"),
        ChatMessage(role="user", content=prompt),
    ]

    try:
        resp = await client.chat(
            messages=messages,
            temperature=0.1,
            max_tokens=2000,
            json_mode=True,
        )
        parsed = parse_json_loose(resp.text)
        if parsed and isinstance(parsed.get("facts"), list):
            for item in parsed["facts"]:
                text = item.get("text", "").strip()
                if text:
                    result.facts.append(ExtractedFact(
                        text=text,
                        section_hint=item.get("section", 0),
                        source_title=title,
                        source_url=url,
                        source_date=published_at or "",
                    ))
        logger.info(f"[事实提取] 文章「{title[:30]}」提取 {len(result.facts)} 条事实")
    except Exception as e:
        logger.error(f"[事实提取] 文章 {article_id} 提取失败: {e}")

    return result


async def collect_source_materials(
    cluster_id: int,
    sections: list,
    db_session=None,
    provider: Optional[str] = None,
) -> Optional[SourceMaterial]:
    """从信息簇搜集事实素材。

    Args:
        cluster_id: InfoCluster ID
        sections: 大纲节列表 (SectionBrief 对象列表)
        db_session: 数据库会话（同步或异步）
        provider: LLM provider，默认 DeepSeek

    Returns:
        SourceMaterial 或 None（无素材时）
    """
    from app.models.raw_info import RawInfo

    # 获取大纲小标题列表
    outline_subtitles = []
    for sec in sections:
        subtitle = sec.subtitle if hasattr(sec, 'subtitle') else sec.get('subtitle', '')
        if subtitle:
            outline_subtitles.append(subtitle)

    if not outline_subtitles:
        logger.warning("[事实提取] 大纲无小标题，跳过")
        return None

    # 查询簇内原始文章
    raw_infos = []
    if db_session:
        from sqlalchemy.ext.asyncio import AsyncSession
        # 异步会话
        if isinstance(db_session, AsyncSession):
            from sqlalchemy import select
            result = await db_session.execute(
                select(RawInfo).where(
                    RawInfo.info_cluster_id == cluster_id,
                    RawInfo.content.isnot(None),
                ).order_by(RawInfo.published_at.desc()).limit(30)
            )
            raw_infos = list(result.scalars().all())
        else:
            # 同步会话
            raw_infos = db_session.query(RawInfo).filter(
                RawInfo.info_cluster_id == cluster_id,
                RawInfo.content.isnot(None),
            ).order_by(RawInfo.published_at.desc()).limit(30).all()

    if not raw_infos:
        logger.warning(f"[事实提取] 簇 {cluster_id} 无原始文章")
        return None

    logger.info(f"[事实提取] 簇 {cluster_id} 共 {len(raw_infos)} 篇文章，开始提取")

    # 用 DeepSeek 做提取（便宜）
    from app.services.llm import get_llm_client
    client = get_llm_client(provider or "deepseek")

    # 并发提取（控制并发数避免过载）
    sem = asyncio.Semaphore(3)

    async def _extract_with_limit(ri):
        async with sem:
            pub_date = ri.published_at.strftime("%Y-%m-%d") if ri.published_at else ""
            return await _extract_facts_from_article(
                article_id=ri.id,
                title=ri.title or "",
                content=ri.content or "",
                url=ri.url or "",
                published_at=pub_date,
                outline_subtitles=outline_subtitles,
                client=client,
            )

    tasks = [_extract_with_limit(ri) for ri in raw_infos]
    article_facts_list = await asyncio.gather(*tasks)

    # 合并去重
    material = _merge_facts(article_facts_list, sections)
    logger.info(
        f"[事实提取] 完成，{material.article_count} 篇文章 → {material.total_facts} 条事实"
    )
    return material


def _merge_facts(article_facts_list: List[ArticleFacts], sections: list) -> SourceMaterial:
    """合并多篇文章的提取结果，去重后按节组织。"""
    facts_by_section: dict = {}  # {section_number: [fact_text, ...]}
    seen_texts = set()  # 用于去重
    total_facts = 0

    # 按发布时间排序（最新的优先，相同事实保留最新来源）
    sorted_articles = sorted(
        [af for af in article_facts_list if af.facts],
        key=lambda a: a.published_at or "",
        reverse=True,
    )

    for af in sorted_articles:
        for fact in af.facts:
            # 简单去重：事实文本前 30 字匹配
            dedup_key = fact.text[:30].strip()
            if dedup_key in seen_texts:
                continue
            seen_texts.add(dedup_key)

            sec = fact.section_hint
            if sec not in facts_by_section:
                facts_by_section[sec] = []
            facts_by_section[sec].append(fact.text)
            total_facts += 1

    return SourceMaterial(
        article_count=len([af for af in article_facts_list if af.facts]),
        total_facts=total_facts,
        facts_by_section=facts_by_section,
        raw_articles=sorted_articles,
    )

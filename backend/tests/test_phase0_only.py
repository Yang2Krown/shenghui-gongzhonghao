"""快速测试：Phase 0 事实提取 + Agent A 正文生成。

只跑 Phase 0 + Agent A，验证事实素材包是否正确注入。
"""

import asyncio
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format='%(name)s | %(message)s')


async def main():
    from app.db.session import SessionLocal
    from app.models.topic_candidate import TopicCandidate
    from app.models.outline import Outline
    from app.services.content_generation.schemas import ContentGenerationInput, SectionBrief
    from app.services.content_generation.source_collector import collect_source_materials

    db = SessionLocal()

    candidate_id = 693
    outline_id = 97

    candidate = db.query(TopicCandidate).filter(TopicCandidate.id == candidate_id).first()
    outline = db.query(Outline).filter(Outline.id == outline_id).first()

    print(f"选题: {candidate.title}")
    print(f"cluster_id: {candidate.info_cluster_id}")
    print()

    sections = []
    for i, sec in enumerate(outline.sections or []):
        sections.append(SectionBrief(
            section_number=i + 1,
            part=sec.get("part", "body"),
            subtitle=sec.get("subtitle", sec.get("title", f"第{i+1}节")),
            description=sec.get("description"),
            core_points=sec.get("core_points", []),
            word_estimate=sec.get("word_count", 500),
        ))

    # Phase 0: 事实提取
    print("=" * 60)
    print("Phase 0: 搜集事实素材")
    print("=" * 60)

    material = await collect_source_materials(
        cluster_id=candidate.info_cluster_id,
        sections=sections,
        db_session=db,
    )

    if material:
        print(f"\n✅ 事实提取成功！")
        print(f"  来源文章数: {material.article_count}")
        print(f"  事实总条数: {material.total_facts}")
        print(f"  按节分布: { {k: len(v) for k, v in material.facts_by_section.items()} }")
        print()
        prompt_text = material.to_prompt_text(sections)
        print("--- 素材包（前 1000 字）---")
        print(prompt_text[:1000])
    else:
        print("\n⚠️ 未提取到事实素材（可能是簇内无文章或提取失败）")

    db.close()


if __name__ == "__main__":
    asyncio.run(main())

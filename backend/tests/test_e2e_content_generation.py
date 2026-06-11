"""端到端测试：正文生成 + Phase 0 事实提取。

运行方式：
  cd backend && .venv/bin/python -m tests.test_e2e_content_generation
"""

import asyncio
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 开启日志以便观察 Phase 0
logging.basicConfig(level=logging.INFO, format='%(name)s | %(message)s')


async def main():
    from app.db.session import SessionLocal
    from app.models.topic_candidate import TopicCandidate
    from app.models.outline import Outline
    from app.services.content_generation.schemas import ContentGenerationInput, SectionBrief
    from app.services.content_generation.orchestrator import generate_content

    db = SessionLocal()

    # 使用 outline_id=110, candidate_id=2
    candidate_id = 2
    outline_id = 110

    candidate = db.query(TopicCandidate).filter(TopicCandidate.id == candidate_id).first()
    outline = db.query(Outline).filter(Outline.id == outline_id).first()

    if not candidate or not outline:
        print("❌ 候选或大纲不存在")
        return

    print(f"选题: {candidate.title}")
    print(f"cluster_id: {candidate.info_cluster_id}")
    print(f"大纲节数: {len(outline.sections or [])}")
    print()

    # 构建 sections
    sections = []
    for i, sec in enumerate(outline.sections or []):
        sections.append(SectionBrief(
            section_number=i + 1,
            part=sec.get("part", "body"),
            subtitle=sec.get("subtitle", sec.get("title", f"第{i+1}节")),
            description=sec.get("description"),
            core_points=sec.get("core_points", []),
            spread_role=sec.get("spread_role"),
            word_estimate=sec.get("word_count", sec.get("word_estimate", 500)),
            notes=sec.get("notes"),
        ))

    inp = ContentGenerationInput(
        topic_title=candidate.title,
        topic_direction=candidate.direction,
        topic_routine=candidate.routine,
        value_promise=candidate.value_promise,
        outline_id=outline_id,
        sections=sections,
        candidate_id=candidate_id,
    )

    print("=" * 60)
    print("开始正文生成（含 Phase 0 事实提取）...")
    print("=" * 60)
    print()

    try:
        output = await generate_content(inp, db_session=db)

        print()
        print("=" * 60)
        print("✅ 正文生成完成！")
        print("=" * 60)
        print(f"最终字数: {output.final_word_count}")
        print(f"节数: {output.section_count}")
        print(f"金句数: {len(output.gold_sentences)}")
        print(f"事实纠错: {output.agent_e_correction_count} 处")
        print(f"Agent A 字数: {output.agent_a_word_count}")
        print()
        print("--- 正文前 500 字 ---")
        print(output.final_text[:500])

    except Exception as e:
        print(f"\n❌ 生成失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())

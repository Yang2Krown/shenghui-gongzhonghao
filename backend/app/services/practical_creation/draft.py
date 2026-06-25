"""成稿：用入选功能点拼大纲，复用 content_generation 流水线出正文。

大纲确认步骤已砍掉 —— 大纲在代码里直接拼（引入 + 实操段×N + 升华），不再过人工。
"""

import logging
from typing import Callable, List, Optional

from app.services.content_generation.orchestrator import generate_content
from app.services.content_generation.schemas import (
    ContentGenerationInput, SectionBrief, StyleParams,
)
from app.services.practical_creation.schemas import ProductResearch

logger = logging.getLogger(__name__)


def build_sections(research: ProductResearch, selected: List[str], template: str) -> List[SectionBrief]:
    """引入(痛点) + 每个入选功能点一个实操段 + 结尾(升华)。"""
    case_led = template == "case"
    secs: List[SectionBrief] = [SectionBrief(
        section_number=1, part="intro", subtitle="引入：戳中读者的痛点场景",
        description="用读者的真实痛点切入，自然引出这个产品",
        core_points=research.advantages[:2], spread_role="钩子", word_estimate=300,
    )]
    n = 2
    picked = [f for f in research.features if f.name in selected] or research.features
    for f in picked:
        # 操作步骤作为核心信息点喂给写手；没抓到步骤就退回到功能说明
        core = list(f.steps) if f.steps else ([f.desc] if f.desc else [])
        secs.append(SectionBrief(
            section_number=n, part="body",
            subtitle=f"实操：{f.name}",
            description=f.desc or f"演示「{f.name}」怎么用",
            core_points=core,
            spread_role="案例展示" if case_led else "高潮",
            word_estimate=550,
            notes="这一段是实操指导：把上面的操作步骤写成读者能照着做的引导，并预留实操截图位",
        ))
        n += 1
    secs.append(SectionBrief(
        section_number=n, part="conclusion", subtitle="结尾：升华",
        description="跳出工具本身，回到读者的长期价值",
        spread_role="收尾", word_estimate=300,
    ))
    return secs


async def generate_practical_draft(
    research: ProductResearch,
    selected: List[str],
    template: str = "tool",
    brief_banned: Optional[List[str]] = None,
    brief_tone: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
    user_id: Optional[int] = None,
) -> dict:
    """返回 {title, text, word_count, sections}。

    爆文套路（research.hot.patterns）走 topic_routine 注入正文创作（agent_a_writer 会读它）。
    """
    sections = build_sections(research, selected, template)
    direction = "工具主线（实操类）" if template != "case" else "案例主线（实操类）"

    style = StyleParams(
        tone=brief_tone or "第一人称、实操向、口语、信息密集",
        banned_words=brief_banned or [],
    )
    routine = research.hot.patterns if research.hot and research.hot.patterns else None
    inp = ContentGenerationInput(
        topic_title=f"{research.product} 实操指南",
        topic_direction=direction,
        topic_routine=routine,
        source_materials=research.to_material_text(),
        sections=sections,
        style_params=style,
        user_id=user_id,
    )
    out = await generate_content(inp, progress_callback=progress_callback)
    return {
        "title": inp.topic_title,
        "text": out.final_text,
        "word_count": out.final_word_count,
        "sections": [s.subtitle for s in sections],
    }


# ── ponytail 自检：大纲拼装逻辑，不调模型 ──
def _demo():
    from app.services.practical_creation.schemas import FeaturePoint
    r = ProductResearch(
        product="某工具", positioning="定位",
        features=[FeaturePoint("A"), FeaturePoint("B"), FeaturePoint("C")],
        advantages=["优势1", "优势2", "优势3"],
    )
    secs = build_sections(r, selected=["A", "C"], template="tool")
    assert secs[0].part == "intro"
    assert secs[-1].part == "conclusion"
    bodies = [s for s in secs if s.part == "body"]
    assert [s.subtitle for s in bodies] == ["实操：A", "实操：C"], bodies  # 只入选 A、C
    assert [s.section_number for s in secs] == [1, 2, 3, 4]              # 连续编号
    # selected 为空时回退到全部功能点
    assert len([s for s in build_sections(r, [], "case") if s.part == "body"]) == 3
    print("draft build_sections self-check OK")


if __name__ == "__main__":
    _demo()

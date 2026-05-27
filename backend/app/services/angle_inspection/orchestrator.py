"""创作角度体检编排。"""

from typing import Callable, Optional

from app.models.topic_candidate import TopicCandidate
from app.services.angle_inspection.agents import audit_angle, audit_rhythm, audit_sources
from app.services.angle_inspection.schemas import CreationAngleInspectionOutput, SelectedTopicInput
from app.services.llm import LLMClient


def _traffic_light_score(verdict: str, *, green: float = 8.5, yellow: float = 6.5, red: float = 3.5) -> float:
    """把红黄绿判定转换成可展示分数。"""

    if "🔴" in verdict or "红" in verdict or "不通过" in verdict:
        return red
    if "🟡" in verdict or "黄" in verdict or "需调整" in verdict:
        return yellow
    if "🟢" in verdict or "绿" in verdict or "通过" in verdict or "有起伏" in verdict:
        return green
    return yellow


def build_selected_topic_input(candidate: TopicCandidate, manual_note: Optional[str] = None) -> SelectedTopicInput:
    """从 TopicCandidate 构建体检输入快照。"""

    score = None
    if getattr(candidate, "score", None):
        score = {
            "pain_point": candidate.score.pain_point,
            "value_density": candidate.score.value_density,
            "propagation": candidate.score.propagation,
            "differentiation": candidate.score.differentiation,
            "freshness": candidate.score.freshness,
            "audience_fit": candidate.score.audience_fit,
            "evidence": candidate.score.evidence or {},
        }

    return SelectedTopicInput(
        candidate_id=candidate.id,
        info_cluster_id=candidate.info_cluster_id,
        title=candidate.title,
        direction=candidate.direction,
        routine=candidate.routine,
        dimension_combo=candidate.dimension_combo or [],
        value_promise=candidate.value_promise,
        angle_note=candidate.angle_note,
        weighted_score=candidate.weighted_score,
        verdict=candidate.verdict,
        score=score,
        manual_note=manual_note,
    )


async def inspect_creation_angle(
    candidate: TopicCandidate,
    *,
    manual_note: Optional[str] = None,
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
    step_offset: int = 0,
) -> CreationAngleInspectionOutput:
    """运行三关创作角度体检。"""

    topic = build_selected_topic_input(candidate, manual_note=manual_note)

    if progress_callback:
        await progress_callback({"event": "step_start", "data": {"step": step_offset + 1, "agent": "沈知衡 · 信息源审计员", "action": "正在检查素材来源和跨领域交叉点...", "avatar": "/agents/angle-a.png"}})
    source_audit = await audit_sources(topic, llm_client=llm_client, model=model)
    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": step_offset + 1, "agent": "信息源审计员"}})

    if progress_callback:
        await progress_callback({"event": "step_start", "data": {"step": step_offset + 2, "agent": "许见微 · 角度陌生化检验员", "action": "正在识别第一直觉角度并生成备选角度...", "avatar": "/agents/angle-b.png"}})
    angle_audit = await audit_angle(topic, source_audit, llm_client=llm_client, model=model)
    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": step_offset + 2, "agent": "角度陌生化检验员"}})

    if progress_callback:
        await progress_callback({"event": "step_start", "data": {"step": step_offset + 3, "agent": "林起伏 · 节奏设计师", "action": "正在设计情绪地图、升番结构和开头结尾...", "avatar": "/agents/angle-c.png"}})
    rhythm_audit = await audit_rhythm(topic, angle_audit, llm_client=llm_client, model=model)
    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": step_offset + 3, "agent": "节奏设计师"}})

    red_count = sum(
        1
        for verdict in [source_audit.verdict, rhythm_audit.verdict]
        if "🔴" in verdict or "红" in verdict
    )
    angle_failed = "不通过" in angle_audit.verdict or "❌" in angle_audit.verdict

    if red_count >= 2:
        overall_verdict = "建议先调整"
        core_suggestion = "至少两关红灯，优先重定角度，再补信息源和节奏。"
    elif angle_failed:
        overall_verdict = "建议先调整"
        core_suggestion = "当前角度接近第一直觉，优先采用备选陌生化角度后再写。"
    else:
        overall_verdict = "可以动笔"
        core_suggestion = "按确认角度推进，大纲必须服从节奏蓝图，不要退回信息搬运。"

    confirmed_angle = angle_audit.current_angle
    if angle_failed and angle_audit.alternative_angles:
        confirmed_angle = angle_audit.alternative_angles[0].angle

    creation_guidance = {
        "confirmed_angle": confirmed_angle,
        "source_hints": source_audit.source_domains,
        "supplement_suggestions": source_audit.supplement_suggestions,
        "rhythm_blueprint": {
            "emotion_map": rhythm_audit.emotion_map,
            "rhythm_curve": rhythm_audit.rhythm_curve,
            "escalation": rhythm_audit.escalation_suggestion,
            "transition_hooks": rhythm_audit.transition_hooks,
        },
        "opening_strategy": rhythm_audit.opening_hook,
        "ending_strategy": rhythm_audit.ending_aftershock,
        "product_placement_strategy": "如果涉及产品/工具，必须藏进故事因果链，让功能展示成为推进情节的必要环节。",
        "alternative_angles": [a.model_dump() for a in angle_audit.alternative_angles],
    }

    source_score = _traffic_light_score(source_audit.verdict)
    angle_score = _traffic_light_score(angle_audit.verdict)
    if angle_audit.unexpected and angle_audit.reasonable and "不通过" not in angle_audit.verdict:
        angle_score = max(angle_score, 8.8)
    elif angle_audit.unexpected or angle_audit.reasonable:
        angle_score = min(angle_score, 6.8)
    rhythm_score = _traffic_light_score(rhythm_audit.verdict)
    total_score = round(source_score * 0.3 + angle_score * 0.45 + rhythm_score * 0.25, 1)

    return CreationAngleInspectionOutput(
        candidate_id=topic.candidate_id,
        title=topic.title,
        source_audit=source_audit,
        source_score=source_score,
        angle_audit=angle_audit,
        angle_score=angle_score,
        rhythm_audit=rhythm_audit,
        rhythm_score=rhythm_score,
        total_score=total_score,
        overall_verdict=overall_verdict,
        core_suggestion=core_suggestion,
        creation_guidance=creation_guidance,
    )

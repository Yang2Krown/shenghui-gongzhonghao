"""创作角度体检 Agent 的 I/O 契约。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SelectedTopicInput(BaseModel):
    """人工选定选题快照。"""

    candidate_id: int
    info_cluster_id: Optional[int] = None
    title: str
    direction: Optional[str] = None
    routine: Optional[str] = None
    dimension_combo: List[Any] = Field(default_factory=list)
    value_promise: Optional[str] = None
    angle_note: Optional[str] = None
    weighted_score: Optional[float] = None
    verdict: Optional[str] = None
    score: Optional[Dict[str, Any]] = None
    manual_note: Optional[str] = None


class SourceAuditOutput(BaseModel):
    """第一关：信息源审计。"""

    verdict: str
    source_domains: List[str] = Field(default_factory=list)
    intersection: str
    supplement_suggestions: List[str] = Field(default_factory=list)


class AlternativeAngle(BaseModel):
    angle: str
    contrast_type: str
    unexpected: bool
    reasonable: bool
    core_tension: str


class AngleAuditOutput(BaseModel):
    """第二关：角度陌生化。"""

    obvious_angles: List[str] = Field(default_factory=list)
    why_avoid: str
    current_angle: str
    verdict: str
    unexpected: bool
    reasonable: bool
    core_tension: str
    alternative_angles: List[AlternativeAngle] = Field(default_factory=list)


class RhythmAuditOutput(BaseModel):
    """第三关：节奏设计。"""

    verdict: str
    emotion_map: str
    rhythm_curve: str
    escalation_suggestion: str
    opening_hook: str
    ending_aftershock: str
    transition_hooks: List[str] = Field(default_factory=list)


class CreationAngleInspectionOutput(BaseModel):
    """三关体检汇总。"""

    candidate_id: int
    title: str
    source_audit: SourceAuditOutput
    source_score: float = Field(default=0.0, ge=0, le=10)
    angle_audit: AngleAuditOutput
    angle_score: float = Field(default=0.0, ge=0, le=10)
    rhythm_audit: RhythmAuditOutput
    rhythm_score: float = Field(default=0.0, ge=0, le=10)
    total_score: float = Field(default=0.0, ge=0, le=10)
    overall_verdict: str
    core_suggestion: str
    creation_guidance: Dict[str, Any] = Field(default_factory=dict)

    def to_prompt_text(self) -> str:
        """压缩成适合放进大纲 Agent prompt 的文本。"""

        guidance = self.creation_guidance or {}
        alt_angles = self.angle_audit.alternative_angles
        return "\n".join([
            "【创作角度体检】",
            f"总判断: {self.overall_verdict}",
            f"核心建议: {self.core_suggestion}",
            f"确认角度: {guidance.get('confirmed_angle') or self.angle_audit.current_angle}",
            f"信息源提示: {guidance.get('source_hints') or self.source_audit.source_domains}",
            f"节奏蓝图: {guidance.get('rhythm_blueprint') or self.rhythm_audit.emotion_map}",
            f"开头策略: {guidance.get('opening_strategy') or self.rhythm_audit.opening_hook}",
            f"结尾策略: {guidance.get('ending_strategy') or self.rhythm_audit.ending_aftershock}",
            f"产品植入策略: {guidance.get('product_placement_strategy') or '如涉及工具/产品，必须服务叙事推进，不做插播式介绍'}",
            "备选角度: " + "；".join(a.angle for a in alt_angles),
        ])

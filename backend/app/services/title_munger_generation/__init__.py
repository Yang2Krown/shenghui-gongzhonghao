"""芒格版标题生成 - 多Agent协作模块"""

from app.services.title_munger_generation.agent_planner import PlannerAgent
from app.services.title_munger_generation.agent_gap import GapAgent
from app.services.title_munger_generation.agent_anchor import AnchorAgent
from app.services.title_munger_generation.agent_conflict import ConflictAgent
from app.services.title_munger_generation.agent_enhancer import EnhancerAgent
from app.services.title_munger_generation.agent_judge import JudgeAgent
from app.services.title_munger_generation.service import MungerTitleGenerationService

__all__ = [
    "PlannerAgent",
    "GapAgent",
    "AnchorAgent",
    "ConflictAgent",
    "EnhancerAgent",
    "JudgeAgent",
    "MungerTitleGenerationService",
]

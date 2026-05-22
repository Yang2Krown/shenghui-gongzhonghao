"""
标题生成模块

实现4 Agent协作流程的标题生成功能。
"""

from app.services.title_generation.agent_a_creator import TitleCreatorAgent
from app.services.title_generation.agent_b_reviewer import TitleReviewerAgent
from app.services.title_generation.agent_c_predictor import ClickPredictorAgent
from app.services.title_generation.agent_d_judge import FinalJudgeAgent
from app.services.title_generation.base import BaseAgent

__all__ = [
    "BaseAgent",
    "TitleCreatorAgent",
    "TitleReviewerAgent",
    "ClickPredictorAgent",
    "FinalJudgeAgent",
]

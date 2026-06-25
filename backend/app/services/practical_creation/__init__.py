"""实操 / 商稿创作流。

两段式：
1. research —— agentic 产品研究（v1 用 Moonshot 自带联网），产出 ProductResearch。
2. draft   —— 用入选功能点拼大纲，复用 content_generation 流水线出成稿。

中间的「研究确认 + 卖点选择」在前端完成，后端只负责返回 / 接收编辑后的结构。
"""

from app.services.practical_creation.schemas import ProductResearch, FeaturePoint, HotResearch
from app.services.practical_creation.research import research_product
from app.services.practical_creation.hot_research import research_hot
from app.services.practical_creation.draft import generate_practical_draft

__all__ = [
    "ProductResearch",
    "FeaturePoint",
    "HotResearch",
    "research_product",
    "research_hot",
    "generate_practical_draft",
]

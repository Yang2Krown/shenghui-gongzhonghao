"""选题挖掘 Agent 包。

Agent A（衍生员）：从 1 条 InfoCluster 衍生 3-8 个候选选题
Agent B（评分员）：对候选选题进行 6 维度评分 + 入选判定
"""

from app.services.topic_mining.agent_a_deriver import derive_candidates
from app.services.topic_mining.agent_b_scorer import score_candidates

__all__ = ["derive_candidates", "score_candidates"]

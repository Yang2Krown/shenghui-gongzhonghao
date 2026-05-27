"""创作角度体检服务。

该模块位于选题候选和大纲生成之间，负责输出可被大纲 Agent 消费的创作指引。
"""

from app.services.angle_inspection.orchestrator import inspect_creation_angle

__all__ = ["inspect_creation_angle"]

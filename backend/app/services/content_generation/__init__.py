"""正文生成服务模块。

4 Agent 协作：
- Agent A（正文创作员）：整篇生成 2500-3000 字正文骨干
- Agent B（金句催化员）：催化 3-5 个金句
- Agent C（去 AI 味改写员）：按《去 AI 味检查清单》净化全文
- Agent D（整合+自检诊断员）：金句嵌入 + 8 维度自检评分 + 诊断报告
"""

from app.services.content_generation.orchestrator import generate_content

__all__ = ["generate_content"]

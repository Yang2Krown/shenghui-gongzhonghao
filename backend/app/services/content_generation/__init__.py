"""正文生成服务模块。

5 Agent 协作：
- Agent A（正文创作员）：整篇生成 2500-3000 字正文骨干
- Agent B（金句催化员）：催化 3-5 个金句
- Agent D（事实总结员）：扫描事实性陈述，提取潜在错误
- Agent E（Kimi 联网纠错员）：联网验证并修正事实错误
- Agent C（去 AI 味改写员）：按《去 AI 味检查清单》净化全文
"""

from app.services.content_generation.orchestrator import generate_content

__all__ = ["generate_content"]

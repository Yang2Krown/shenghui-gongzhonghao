"""统一封装 agent-reach CLI / mcporter subprocess 调用。

复用现有 services/agent_reach_client.py 的方法（feedparser / Jina Reader / Exa mcporter）。
后续如果要新增 agent-reach CLI 命令，集中在这里。
"""

from app.services.agent_reach_client import agent_reach_client

__all__ = ["agent_reach_client"]

"""
缺口 Agent - 芒格版标题生成 Step 1.1

职责：信息缺口构造
输入：定位语
输出：2-3条候选标题（信息缺口维度）
"""

from typing import Dict, Any, List
import logging
import re

from app.services.title_generation.base import BaseAgent

logger = logging.getLogger(__name__)


class GapAgent(BaseAgent):
    """缺口 Agent - 信息缺口构造"""

    def __init__(self):
        super().__init__()
        self.agent_name = "缺口 Agent"
        self.agent_role = "信息缺口专家"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        positioning = kwargs.get("positioning", "")
        return await self.generate_gap_titles(positioning)

    async def generate_gap_titles(self, positioning: str) -> Dict[str, Any]:
        """生成信息缺口维度标题"""
        logger.info("缺口 Agent 开始生成")

        response = await self.call_ai_model(
            prompt=self._build_prompt(positioning),
            system_prompt=self._get_system_prompt(),
            temperature=0.8,
        )

        titles = self._parse_titles_robust(response)

        logger.info(f"缺口 Agent 生成 {len(titles)} 条标题")
        return {"titles": titles, "raw_response": response}

    def _build_prompt(self, positioning: str) -> str:
        return f"""基于以下定位语，生成 2-3 条候选标题：

定位语：{positioning}

要求：
- 方向感充足（读者知道话题是什么）
- 关键变量藏住（读者必须点进来才知道答案）
- 每条标题 ≤ 20个汉字（含标点）
- 不得使用"震惊""必看""颠覆"等情绪词

输出格式（严格按以下格式，每行一条）：
TITLE||标题内容||信息缺口"""

    def _get_system_prompt(self) -> str:
        return """你是一个标题撰写专家，专攻"信息缺口"维度。

核心原理：不确定性 = 危险信号 → 读者本能地想消除缺口
操作公式：用具体名词给方向 + 用否定句/悬置句藏答案

规则：
- 方向感充足（读者知道话题是什么）
- 关键变量藏住（读者必须点进来才知道答案）
- 每条标题 ≤ 20个汉字（含标点）
- 不得使用"震惊""必看""颠覆"等情绪词"""

    def _parse_titles_robust(self, response: str) -> List[Dict[str, str]]:
        """解析标题，支持多种格式"""
        titles = []

        # Try TITLE|| format first
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("TITLE||"):
                parts = line.split("||")
                if len(parts) >= 2:
                    title_text = parts[1].strip()
                    if title_text:
                        titles.append({"title": title_text, "dimension": "信息缺口"})

        # Fallback to numeric/XMl parsing
        if not titles:
            titles = self._parse_titles_xml(response)

        return titles

    def _parse_titles_xml(self, response: str) -> List[Dict[str, str]]:
        """从 XML 标签或数字列表中解析"""
        titles = []
        content = ""

        # Try <titles> block
        pattern = r"<titles>(.*?)</titles>"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            content = match.group(1)
        else:
            content = response

        for line in content.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if line and (line[0].isdigit() or line.startswith("-")):
                title_text = re.sub(r'^[\d\.\-\s]+', '', line).strip()
                # Remove trailing annotations
                title_text = re.sub(r'[（(]\d+[字字符]+[）)]$', '', title_text).strip()
                title_text = re.sub(r'\s*\|\s*.*$', '', title_text).strip()

                if title_text and len(title_text) <= 25:
                    titles.append({"title": title_text, "dimension": "信息缺口"})

        return titles

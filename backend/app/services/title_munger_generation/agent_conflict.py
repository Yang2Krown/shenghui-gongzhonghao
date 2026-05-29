"""
冲突 Agent - 芒格版标题生成 Step 1.3

职责：认知冲突制造
输入：定位语
输出：2-3条候选标题（世界模型更新维度）
"""

from typing import Dict, Any, List
import logging
import re

from app.services.title_generation.base import BaseAgent

logger = logging.getLogger(__name__)


class ConflictAgent(BaseAgent):
    """冲突 Agent - 认知冲突制造"""

    def __init__(self):
        super().__init__()
        self.agent_name = "冲突 Agent"
        self.agent_role = "认知冲突专家"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        positioning = kwargs.get("positioning", "")
        return await self.generate_conflict_titles(positioning)

    async def generate_conflict_titles(self, positioning: str) -> Dict[str, Any]:
        """生成认知冲突维度标题"""
        logger.info("冲突 Agent 开始生成")

        response = await self.call_ai_model(
            prompt=self._build_prompt(positioning),
            system_prompt=self._get_system_prompt(),
            temperature=0.8,
        )

        assumption = self._parse_xml(response, "assumption")
        titles = self._parse_titles_robust(response)

        logger.info(f"冲突 Agent 生成 {len(titles)} 条标题")
        return {
            "titles": titles,
            "assumption": assumption,
            "raw_response": response,
        }

    def _build_prompt(self, positioning: str) -> str:
        return f"""基于以下定位语，生成 2-3 条候选标题：

定位语：{positioning}

要求：
- 先识别目标读者对该话题最普遍的假设
- 然后否定该假设，或给出矛盾事实
- "为什么"句式天然适合，但"问题出在"也有效

输出格式：
<assumption>读者的默认假设：……</assumption>
TITLE||标题内容||认知冲突
TITLE||标题内容||认知冲突"""

    def _get_system_prompt(self) -> str:
        return """你是一个标题撰写专家，专攻"世界模型更新"维度。

核心原理：预期违背 → 强制重评估 → 读者无法忽略
操作方式：找到读者的默认因果模型，在标题中打破它

规则：
- 先识别目标读者对该话题最普遍的假设
- 然后否定该假设，或给出矛盾事实
- "为什么"句式天然适合，但"问题出在"也有效"""

    def _parse_titles_robust(self, response: str) -> List[Dict[str, str]]:
        """解析标题"""
        titles = []

        # Try TITLE|| format first
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("TITLE||"):
                parts = line.split("||")
                if len(parts) >= 2:
                    title_text = parts[1].strip()
                    if title_text:
                        titles.append({"title": title_text, "dimension": "认知冲突"})

        # Fallback to XML/numeric parsing
        if not titles:
            pattern = r"<titles>(.*?)</titles>"
            match = re.search(pattern, response, re.DOTALL)
            content = match.group(1) if match else response

            for line in content.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                if line and (line[0].isdigit() or line.startswith("-")):
                    title_text = re.sub(r'^[\d\.\-\s]+', '', line).strip()
                    title_text = re.sub(r'[（(]\d+[字字符]+[）)]$', '', title_text).strip()
                    title_text = re.sub(r'\s*\|\s*.*$', '', title_text).strip()
                    if title_text:
                        titles.append({"title": title_text, "dimension": "认知冲突"})

        return titles

    def _parse_xml(self, response: str, tag: str) -> str:
        pattern = f"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, response, re.DOTALL)
        return match.group(1).strip() if match else ""

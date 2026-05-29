"""
锚点 Agent - 芒格版标题生成 Step 1.2

职责：社会位置锚定
输入：定位语
输出：2-3条候选标题（社会位置维度）
"""

from typing import Dict, Any, List
import logging
import re

from app.services.title_generation.base import BaseAgent

logger = logging.getLogger(__name__)


class AnchorAgent(BaseAgent):
    """锚点 Agent - 社会位置锚定"""

    def __init__(self):
        super().__init__()
        self.agent_name = "锚点 Agent"
        self.agent_role = "社会位置锚定专家"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        positioning = kwargs.get("positioning", "")
        return await self.generate_anchor_titles(positioning)

    async def generate_anchor_titles(self, positioning: str) -> Dict[str, Any]:
        """生成社会位置维度标题"""
        logger.info("锚点 Agent 开始生成")

        titles_text = await self.call_ai_model(
            prompt=self._build_prompt(positioning),
            system_prompt=self._get_system_prompt(),
            temperature=0.8,
        )

        titles = self._parse_titles_robust(titles_text)

        logger.info(f"锚点 Agent 生成 {len(titles)} 条标题")
        return {"titles": titles, "raw_response": titles_text}

    def _build_prompt(self, positioning: str) -> str:
        return f"""基于以下定位语，生成 2-3 条候选标题：

定位语：{positioning}

要求：
- 必须包含一个身份锚点
- 锚点精度："窄到让目标群体感到被点名，宽到让相邻群体也觉得相关"
- 目标读者：科技/AI行业从业者

输出格式（严格按以下格式，每行一条）：
TITLE||标题内容||锚点类型：职业/行为/处境"""

    def _get_system_prompt(self) -> str:
        return """你是一个标题撰写专家，专攻"社会位置"维度。

核心原理：群体排斥 = 生存威胁 → 读者需要确认"这跟我有关"
三种锚点：职业角色 / 行为描述 / 处境描述

规则：
- 必须包含一个身份锚点
- 锚点精度："窄到让目标群体感到被点名，宽到让相邻群体也觉得相关"
- 目标读者：科技/AI行业从业者"""

    def _parse_titles_robust(self, response: str) -> List[Dict[str, str]]:
        """解析标题，支持多种格式"""
        titles = []

        # First try TITLE|| format
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("TITLE||"):
                parts = line.split("||")
                if len(parts) >= 2:
                    title_text = parts[1].strip()
                    anchor_type = ""
                    if len(parts) >= 3:
                        anchor_type = parts[2].replace("锚点类型：", "").replace("锚点类型:", "").strip()
                    if title_text:
                        titles.append({"title": title_text, "dimension": "社会位置", "anchor_type": anchor_type})

        # Fallback to XML parsing
        if not titles:
            titles = self._parse_titles_xml(response)

        return titles

    def _parse_titles_xml(self, response: str) -> List[Dict[str, str]]:
        """从 XML 标签中解析标题"""
        titles = []

        # Try <titles> block
        pattern = r"<titles>(.*?)</titles>"
        match = re.search(pattern, response, re.DOTALL)
        lines = []
        if match:
            lines = match.group(1).strip().split("\n")
        else:
            lines = response.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Remove leading numbering
            title_text = re.sub(r'^[\d\.\-\s]+', '', line).strip()

            # Extract anchor type
            anchor_type = ""
            type_match = re.search(r'\|\s*锚点类型[：:]\s*(.*?)$', title_text)
            if type_match:
                anchor_type = type_match.group(1).strip()

            # Clean: remove everything after | separator
            title_text = re.sub(r'\s*\|\s*锚点类型[：:].*$', '', title_text).strip()
            # Remove trailing (X字) or (X字符)
            title_text = re.sub(r'[（(]\d+[字字符]+[）)]$', '', title_text).strip()
            # Remove any remaining trailing parenthetical
            title_text = re.sub(r'[（(][^）)]*[）)]$', '', title_text).strip()

            # Count actual Chinese chars
            cn_chars = self._count_chinese(title_text)
            if title_text:
                titles.append({"title": title_text, "dimension": "社会位置", "anchor_type": anchor_type})

        return titles

    def _count_chinese(self, text: str) -> List[str]:
        """Count Chinese characters and Chinese punctuation"""
        import unicodedata
        chars = []
        for c in text:
            if '一' <= c <= '鿿' or '　' <= c <= '〿' or '＀' <= c <= '￯':
                chars.append(c)
        return chars

    def _parse_titles(self, response: str) -> List[Dict[str, str]]:
        """Legacy parser"""
        return self._parse_titles_xml(response)

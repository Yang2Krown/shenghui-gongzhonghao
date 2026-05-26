"""
策划 Agent - 芒格版标题生成 Step 0

职责：定位语提取
输入：文章全文 / 内容摘要
输出：一句定位语（含反直觉判断或具体归因）
"""

from typing import Dict, Any, Optional
import logging

from app.services.title_generation.base import BaseAgent

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
    """策划 Agent - 定位语提取"""

    def __init__(self):
        super().__init__()
        self.agent_name = "策划 Agent"
        self.agent_role = "内容定位专家"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        content = kwargs.get("content", "")
        feedback = kwargs.get("feedback", "")
        return await self.extract_positioning(content, feedback)

    async def extract_positioning(
        self,
        content: str,
        feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """提取定位语"""
        logger.info("策划 Agent 开始提取定位语")

        prompt = self._build_prompt(content, feedback)

        response = await self.call_ai_model(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.7,
        )

        result = self.parse_xml_response(response, "positioning")
        check = self.parse_xml_response(response, "check")

        positioning = result.get("positioning", "")
        check_text = check.get("check", "")

        logger.info(f"策划 Agent 定位语: {positioning}")

        return {
            "positioning": positioning,
            "check": check_text,
            "raw_response": response,
        }

    def _get_system_prompt(self) -> str:
        return """你是一个内容定位专家。阅读以下文章内容，用一句话回答：
"这篇文章让读者知道了什么他原来不知道的东西？"

要求：
- 必须包含一个反直觉判断或具体归因
- 不能是内容简介（如"介绍了AI Agent的现状"）
- 必须有信息增量

输出格式：
<positioning>定位语</positioning>
<check>是否包含反直觉判断：是/否 | 是否有具体归因：是/否</check>"""

    def _build_prompt(self, content: str, feedback: Optional[str] = None) -> str:
        prompt = f"""【文章内容】
{content}

【你的任务】
阅读以上文章内容，用一句话回答：
"这篇文章让读者知道了什么他原来不知道的东西？"

要求：
- 必须包含一个反直觉判断或具体归因
- 不能是内容简介（如"介绍了AI Agent的现状"）
- 必须有信息增量"""

        if feedback:
            prompt += f"""

【上一轮反馈（需要针对性改进）】
{feedback}"""

        return prompt

    def parse_xml_response(self, response: str, tag: str) -> Dict[str, str]:
        """简单解析 XML 标签内容"""
        import re
        result = {}
        pattern = f"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            result[tag] = match.group(1).strip()
        return result

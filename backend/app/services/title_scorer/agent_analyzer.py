"""
拆解 Agent - 芒格版标题评分 Step 0

职责：结构化解读
输入：用户提供的标题 + 文章摘要（可选）
输出：拆解报告（供下游所有 Agent 使用）
"""

from typing import Dict, Any, Optional
import logging
import re

from app.services.title_generation.base import BaseAgent

logger = logging.getLogger(__name__)


class AnalyzerAgent(BaseAgent):
    """拆解 Agent - 结构化解读"""

    def __init__(self):
        super().__init__()
        self.agent_name = "拆解 Agent"
        self.agent_role = "标题结构分析专家"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        title = kwargs.get("title", "")
        summary = kwargs.get("summary", "")
        return await self.analyze(title, summary)

    async def analyze(self, title: str, summary: Optional[str] = None) -> Dict[str, Any]:
        """执行结构化拆解"""
        logger.info(f"拆解 Agent 开始分析: {title}")

        if not title or not title.strip():
            return {"error": "标题为空或无意义字符", "analysis": {}}

        prompt = f"""分析维度：
1. 字数统计：精确到每个汉字和标点
2. 句式识别：陈述句 / 疑问句 / 否定句 / 祈使句 / 悬置句
3. 关键词提取：名词、动词、形容词分别列出
4. 名字识别：是否包含公司名/人名/产品名？是谁？
5. 数字识别：是否包含数字？什么类型的数字？
6. 因果结构：是否包含因果词（为什么/原因/问题出在）？
7. 身份锚点：是否指向特定人群？谁？用什么方式锚定的？
8. 情绪词检测：是否包含"震惊/必看/颠覆/重磅"等词？
9. 信息完整度：标题是否已经把答案说完了（缺口为零）？

输入标题：{title}"""

        if summary:
            prompt += f"\n文章摘要（如有）：{summary}"

        prompt += """

输出格式：
<analysis>
字数：X
句式：……
关键词：名词[…] 动词[…] 形容词[…]
名字：有/无 → ……
数字：有/无 → ……
因果结构：有/无 → ……
身份锚点：有/无 → 类型：…… → 指向人群：……
情绪词：有/无 → ……
信息完整度：完整/有缺口/缺口过大
</analysis>"""

        response = await self.call_ai_model(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.3,
        )

        analysis_text = self._parse_xml(response, "analysis")

        # Parse raw analysis into structured data
        word_count = self._extract_value(analysis_text, "字数")
        sentence_type = self._extract_value(analysis_text, "句式")
        keywords = self._extract_value(analysis_text, "关键词")
        has_name = self._extract_value(analysis_text, "名字")
        has_number = self._extract_value(analysis_text, "数字")
        has_causal = self._extract_value(analysis_text, "因果结构")
        anchor = self._extract_value(analysis_text, "身份锚点")
        emotion_words = self._extract_value(analysis_text, "情绪词")
        completeness = self._extract_value(analysis_text, "信息完整度")

        logger.info(f"拆解 Agent 完成，字数: {word_count}")

        return {
            "analysis": {
                "word_count": word_count,
                "sentence_type": sentence_type,
                "keywords": keywords,
                "has_name": has_name,
                "has_number": has_number,
                "has_causal": has_causal,
                "anchor": anchor,
                "emotion_words": emotion_words,
                "completeness": completeness,
                "raw": analysis_text,
            },
            "raw_response": response,
        }

    def _get_system_prompt(self) -> str:
        return """你是一个标题结构分析专家。对输入的标题进行结构化拆解，不做评价，只做客观描述。

分析维度：
1. 字数统计：精确到每个汉字和标点
2. 句式识别：陈述句 / 疑问句 / 否定句 / 祈使句 / 悬置句
3. 关键词提取：名词、动词、形容词分别列出
4. 名字识别：是否包含公司名/人名/产品名？是谁？
5. 数字识别：是否包含数字？什么类型的数字？
6. 因果结构：是否包含因果词（为什么/原因/问题出在）？
7. 身份锚点：是否指向特定人群？谁？用什么方式锚定的？
8. 情绪词检测：是否包含"震惊/必看/颠覆/重磅"等词？
9. 信息完整度：标题是否已经把答案说完了（缺口为零）？"""

    def _parse_xml(self, response: str, tag: str) -> str:
        pattern = f"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, response, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_value(self, text: str, key: str) -> str:
        pattern = rf"{key}[：:]\s*(.*?)(?:\n|$)"
        match = re.search(pattern, text)
        return match.group(1).strip() if match else ""

"""
增强 Agent - 芒格版标题生成 Step 2

职责：芒格倾向叠加
输入：Step 1 全部候选标题（6-9条）
输出：增强后的 Top 5 标题
"""

from typing import Dict, Any, List
import logging
import re

from app.services.title_generation.base import BaseAgent

logger = logging.getLogger(__name__)


class EnhancerAgent(BaseAgent):
    """增强 Agent - 芒格倾向叠加"""

    def __init__(self):
        super().__init__()
        self.agent_name = "增强 Agent"
        self.agent_role = "标题优化专家"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        all_titles = kwargs.get("all_titles", [])
        return await self.enhance_titles(all_titles)

    async def enhance_titles(self, all_titles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """增强并选择 Top 5 标题"""
        logger.info(f"增强 Agent 开始处理，输入 {len(all_titles)} 条标题")

        titles_text = "\n".join([
            f"{i+1}. {t.get('title', '')}（{t.get('dimension', '')}）"
            for i, t in enumerate(all_titles)
        ])

        prompt = f"""对每条候选标题依次做三轮检查并尝试增强：

【A 联想检查】能否自然地嵌入一个高势能名字（公司/人物/产品）？
  规则：名字要大，语气要小。克制 > 夸张。

【B 对比检查】能否前置一个天然对比结构（数字/时间/结果反转）？
  规则：对比两端都在读者想象力射程内。方向相反效果最强。

【C 因果检查】能否加入因果承诺（为什么/原因是/问题出在/真正决定X的是）？
  规则：不一定用"为什么"，"问题出在哪"偏实操，对技术人群更有行动感。

约束：
- 增强后仍须 ≤ 20个汉字
- 不可使用"震惊""必看""颠覆"等词
- 如果增强导致超字数或降低质量，保留原版

输入标题列表：
{titles_text}

输出格式（选出最佳5条，严格按以下格式，每行一条）：
ENHANCED||标题内容||维度：缺口/锚点/冲突||增强：联想/对比/因果/无"""

        response = await self.call_ai_model(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.7,
        )

        enhanced = self._parse_enhanced(response)

        # If ENHANCED format failed, try XML fallback
        if not enhanced:
            enhanced = self._parse_enhanced_xml(response)

        logger.info(f"增强 Agent 输出 Top {len(enhanced)}")
        return {"top5": enhanced, "raw_response": response}

    def _get_system_prompt(self) -> str:
        return """你是一个标题优化专家。对每条候选标题依次做三轮检查并尝试增强：

【A 联想检查】能否自然地嵌入一个高势能名字（公司/人物/产品）？
  规则：名字要大，语气要小。克制 > 夸张。

【B 对比检查】能否前置一个天然对比结构（数字/时间/结果反转）？
  规则：对比两端都在读者想象力射程内。方向相反效果最强。

【C 因果检查】能否加入因果承诺（为什么/原因是/问题出在/真正决定X的是）？
  规则：不一定用"为什么"，"问题出在哪"偏实操，对技术人群更有行动感。

约束：
- 增强后仍须 ≤ 20个汉字
- 不可使用"震惊""必看""颠覆"等词
- 如果增强导致超字数或降低质量，保留原版

输出格式：每行一条 ENHANCED||标题内容||维度：缺口/锚点/冲突||增强：联想/对比/因果/无"""

    def _parse_enhanced(self, response: str) -> List[Dict[str, Any]]:
        """解析 ENHANCED|| 格式"""
        titles = []
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("ENHANCED||"):
                parts = line.split("||")
                if len(parts) >= 2:
                    title_text = parts[1].strip()

                    # Extract dimension
                    dimension = ""
                    if len(parts) >= 3:
                        dim_part = parts[2].strip()
                        for d in ["缺口", "锚点", "冲突"]:
                            if d in dim_part:
                                dimension = d
                                break

                    # Extract enhancement
                    enhancement = "无"
                    if len(parts) >= 4:
                        enh_part = parts[3].strip()
                        for e in ["联想", "对比", "因果"]:
                            if e in enh_part:
                                if enhancement == "无":
                                    enhancement = e
                                else:
                                    enhancement += f",{e}"

                    if title_text and len(title_text) <= 25:
                        titles.append({
                            "title": title_text,
                            "dimension": dimension,
                            "enhancement": enhancement,
                        })
        return titles

    def _parse_enhanced_xml(self, response: str) -> List[Dict[str, Any]]:
        """XML fallback parser"""
        titles = []
        pattern = r"<enhanced>(.*?)</enhanced>"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            content = match.group(1)
            for line in content.strip().split("\n"):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-")):
                    title_text = re.sub(r'^[\d\.\-\s]+', '', line)

                    enhance_match = re.search(r'\|\s*增强项[：:]\s*(.*?)$', title_text)
                    enhancement = enhance_match.group(1).strip() if enhance_match else "无"

                    dim_match = re.search(r'\|\s*命中维度[：:]\s*(.*?)(?:\s*\|\s*|$)', title_text)
                    dimension = dim_match.group(1).strip() if dim_match else ""

                    title_text = re.sub(r'\s*\|\s*命中维度[：:].*$', '', title_text).strip()
                    title_text = re.sub(r'\s*\|\s*增强项[：:].*$', '', title_text).strip()
                    title_text = re.sub(r'[（(]\d+[字字符]+[）)]$', '', title_text).strip()

                    if title_text and len(title_text) <= 25:
                        titles.append({
                            "title": title_text,
                            "dimension": dimension,
                            "enhancement": enhancement,
                        })
        return titles

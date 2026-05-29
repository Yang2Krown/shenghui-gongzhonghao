"""
审判 Agent - 芒格版标题生成 Step 3

职责：拇指测试 + 红线审查
输入：Top 5 增强标题
输出：最终排序 + 通过/不通过
"""

from typing import Dict, Any, List, Optional
import logging
import re

from app.services.title_generation.base import BaseAgent

logger = logging.getLogger(__name__)


class JudgeAgent(BaseAgent):
    """审判 Agent - 最终审核"""

    def __init__(self):
        super().__init__()
        self.agent_name = "审判 Agent"
        self.agent_role = "最终审核官"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        top5 = kwargs.get("top5", [])
        return await self.verdict(top5)

    async def verdict(self, top5: List[Dict[str, Any]]) -> Dict[str, Any]:
        """执行最终审判"""
        logger.info(f"审判 Agent 开始审核 {len(top5)} 条标题")

        titles_text = "\n".join([
            f"{i+1}. {t.get('title', '')}（{t.get('dimension', '')}）"
            for i, t in enumerate(top5)
        ])

        prompt = f"""对每条标题执行两项测试：

【拇指测试】
场景：30出头、一线城市互联网公司、正在刷订阅号、拇指快速滑动、
标题出现在屏幕上的时间大约0.8秒。
判定：
- 👆 划过去了（0维命中）→ 淘汰
- 🤔 犹豫了（1维命中）→ 备选，建议回 Step 2
- 👇 点进去了（2+维命中）→ 通过

【红线审查】
1. 是否贩卖焦虑？（"你的同龄人正在抛弃你"类）→ 否决
2. 标题承诺能否被正文兑现？→ 存疑则降级
3. 是否使用"震惊/必看/颠覆"等操控词？→ 否决
4. 是否命名了一个"未被命名的状态"？→ 加分

输入标题：
{titles_text}

== 重要：每行输出只包含一个标题的完整信息，用 | 分隔 ==
输出格式（严格按以下格式，每行一个标题）：
VERDICT||标题内容||拇指：👆/🤔/👇||红线：通过/未通过(原因)||最终判定：发布/备选/淘汰
VERDICT||标题内容||拇指：👆/🤔/👇||红线：通过/未通过(原因)||最终判定：发布/备选/淘汰

FINAL_PICK||推荐发布的标题（如有）"""

        response = await self.call_ai_model(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.3,
        )

        verdicts = self._parse_verdicts(response)
        final_pick = self._parse_final_pick(response)

        # 判断是否全部淘汰
        all_rejected = all(
            v.get("final_verdict") == "淘汰" for v in verdicts
        )

        # 提取失败原因
        failure_reasons = []
        if all_rejected:
            for v in verdicts:
                if v.get("reason"):
                    failure_reasons.append(v["reason"])

        passed_titles = [
            v for v in verdicts
            if v.get("final_verdict") in ("发布", "备选")
        ]

        logger.info(f"审判 Agent 完成，通过 {len(passed_titles)} 条，全部淘汰: {all_rejected}")

        return {
            "verdicts": verdicts,
            "final_pick": final_pick,
            "all_rejected": all_rejected,
            "failure_reasons": failure_reasons,
            "passed": len(passed_titles) > 0,
            "raw_response": response,
        }

    def _get_system_prompt(self) -> str:
        return """你是最终审核官。对每条标题执行两项测试：

【拇指测试】
场景：30出头、一线城市互联网公司、正在刷订阅号、拇指快速滑动、
标题出现在屏幕上的时间大约0.8秒。
判定：
- 👆 划过去了（0维命中）→ 淘汰
- 🤔 犹豫了（1维命中）→ 备选，建议回 Step 2
- 👇 点进去了（2+维命中）→ 通过

【红线审查】
1. 是否贩卖焦虑？（"你的同龄人正在抛弃你"类）→ 否决
2. 标题承诺能否被正文兑现？→ 存疑则降级
3. 是否使用"震惊/必看/颠覆"等操控词？→ 否决
4. 是否命名了一个"未被命名的状态"？→ 加分

输出请严格使用以下格式，每行一条：
VERDICT||标题内容||拇指：👆/🤔/👇||红线：通过/未通过||最终判定：发布/备选/淘汰"""

    def _parse_final_pick(self, response: str) -> str:
        """从 VERDICT 格式中提取 final_pick，也尝试 XML 回退"""
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("FINAL_PICK||"):
                return line.replace("FINAL_PICK||", "").strip()
        # Fallback to XML
        pattern = r"<final_pick>(.*?)</final_pick>"
        match = re.search(pattern, response, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _parse_verdicts(self, response: str) -> List[Dict[str, Any]]:
        """解析 VERDICT 格式，也支持 XML 回退"""
        verdicts = []

        # Try VERDICT|| format first
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("VERDICT||"):
                parts = line.split("||")
                if len(parts) >= 5:
                    title_text = parts[1].strip()

                    thumb = "👆"
                    if "👇" in parts[2]:
                        thumb = "👇"
                    elif "🤔" in parts[2]:
                        thumb = "🤔"

                    redline = parts[3].replace("红线：", "").strip() if "红线：" in parts[3] else parts[3].strip()

                    final_verdict = "淘汰"
                    if "发布" in parts[4]:
                        final_verdict = "发布"
                    elif "备选" in parts[4]:
                        final_verdict = "备选"

                    verdicts.append({
                        "title": title_text,
                        "thumb": thumb,
                        "redline": redline,
                        "word_count": 0,
                        "final_verdict": final_verdict,
                        "reason": redline if "未通过" in redline else "",
                    })

        # If VERDICT format didn't work, fallback to XML parsing
        if not verdicts:
            pattern = r"<verdict>(.*?)</verdict>"
            match = re.search(pattern, response, re.DOTALL)
            if match:
                content = match.group(1)
                lines = content.strip().split("\n")
                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    if line and (line[0].isdigit() or line.startswith("-")):
                        title_text = ""
                        thumb = "👆"
                        redline = "通过"
                        word_count = 0
                        final_verdict = "淘汰"

                        # Parse main line
                        title_match = re.search(r'[\d\.\-\s]*(.*?)\s*\|', line)
                        if title_match:
                            title_text = title_match.group(1).strip()

                        thumb_match = re.search(r'拇指[：:]\s*([👆🤔👇])', line)
                        if thumb_match:
                            thumb = thumb_match.group(1)

                        redline_match = re.search(r'红线[：:]\s*([^|]+)', line)
                        if redline_match:
                            redline = redline_match.group(1).strip()

                        wc_match = re.search(r'字数[：:]\s*(\d+)', line)
                        if wc_match:
                            word_count = int(wc_match.group(1))

                        # Check next line for final verdict
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            verdict_match = re.search(r'最终判定[：:]\s*(发布|备选|淘汰)', next_line)
                            if verdict_match:
                                final_verdict = verdict_match.group(1)
                                i += 1  # skip next line

                        verdicts.append({
                            "title": title_text,
                            "thumb": thumb,
                            "redline": redline,
                            "word_count": word_count,
                            "final_verdict": final_verdict,
                            "reason": redline if "未通过" in redline else "",
                        })
                    i += 1

        return verdicts

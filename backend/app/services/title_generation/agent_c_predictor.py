"""
Agent C - 读者点击预测员

角色定位: 目标读者本人（28岁互联网产品经理）
核心任务: 模拟读者场景，预测点击意愿
"""

from typing import Dict, Any, List
import logging
from pathlib import Path

from app.services.title_generation.base import BaseAgent
from app.schemas.title_generation import TopicInfo, OutlineInfo

logger = logging.getLogger(__name__)

# 获取当前文件所在目录
CURRENT_DIR = Path(__file__).parent

# 目标读者画像
READER_PROFILE = {
    "age": 28,
    "gender": "男",
    "occupation": "互联网产品经理",
    "work_years": 5,
    "ai_tools": ["Claude", "ChatGPT", "Cursor"],
    "subscriptions": ["路人甲TM", "其他10+科技/职场公众号"],
    "reading_habit": "每天早上和晚上刷一遍订阅号信息流，平均花30秒决定打开哪些",
}


class ClickPredictorAgent(BaseAgent):
    """
    Agent C - 读者点击预测员
    
    角色: 目标读者本人（28岁互联网产品经理）
    任务: 模拟读者场景，预测点击意愿
    """
    
    def __init__(self):
        """初始化读者点击预测员"""
        super().__init__()
        self.agent_name = "读者点击预测员"
        self.agent_role = "目标读者(28岁互联网产品经理)"
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行点击预测任务
        
        Args:
            top5: Top 5候选列表
            topic: 选题信息
            outline: 大纲信息
            
        Returns:
            点击预测结果
        """
        top5 = kwargs.get("top5", [])
        topic = kwargs.get("topic")
        outline = kwargs.get("outline")
        
        return await self.predict_clicks(top5, topic, outline)
    
    async def predict_clicks(
        self,
        top5: List[Dict[str, Any]],
        topic: TopicInfo,
        outline: OutlineInfo,
    ) -> Dict[str, Any]:
        """
        预测点击意愿
        
        模拟订阅号信息流场景，对Top 5逐个预测点击意愿。
        
        Args:
            top5: Top 5候选列表
            topic: 选题信息
            outline: 大纲信息
            
        Returns:
            点击预测结果
        """
        logger.info(f"Agent C 开始预测点击，候选数量: {len(top5)}")
        
        # 构建预测提示词
        prompt = self._build_prediction_prompt(top5, topic, outline)
        
        # 调用AI模型
        response = await self.call_ai_model(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.5,  # 中等温度，模拟真实反应
        )
        
        # 解析响应
        result = self.parse_json_response(response)
        
        # 整理预测结果
        predictions = self._format_predictions(result.get("predictions", []), top5)
        
        logger.info(f"Agent C 预测完成，平均点击意愿: {self._calculate_average_click(predictions)}")
        
        return {
            "predictions": predictions,
            "reader_profile": READER_PROFILE,
            "raw_response": response,
        }
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        prompt_file = CURRENT_DIR / "prompts" / "agent_c_system.txt"
        if prompt_file.exists():
            template = prompt_file.read_text(encoding="utf-8")
            return template.format(
                age=READER_PROFILE['age'],
                occupation=READER_PROFILE['occupation'],
                gender=READER_PROFILE['gender'],
                work_years=READER_PROFILE['work_years'],
                ai_tools=' / '.join(READER_PROFILE['ai_tools']),
                subscriptions=READER_PROFILE['subscriptions'][0],
                other_subscriptions=len(READER_PROFILE['subscriptions']) - 1,
                reading_habit=READER_PROFILE['reading_habit'],
            )
        # 回退到硬编码版本
        return f"""你的身份：{READER_PROFILE['age']}岁互联网{READER_PROFILE['occupation']}，{READER_PROFILE['gender']}，工作{READER_PROFILE['work_years']}年。
日常使用{' / '.join(READER_PROFILE['ai_tools'])}等AI工具。
订阅了"{READER_PROFILE['subscriptions'][0]}"和其他{len(READER_PROFILE['subscriptions']) - 1}个科技/职场公众号。
{READER_PROFILE['reading_habit']}

你的任务：
模拟自己在刷订阅号信息流时的真实反应，预测对每个标题的点击意愿。

你的原则：
- 真实即可，不要为了"政治正确"给所有候选打高分
- 如果某个标题让你瞬间想划走，请直说"看到就划"
- 说明会点/不会点的具体原因"""
    
    def _build_prediction_prompt(
        self,
        top5: List[Dict[str, Any]],
        topic: TopicInfo,
        outline: OutlineInfo,
    ) -> str:
        """
        构建预测提示词
        
        Args:
            top5: Top 5候选列表
            topic: 选题信息
            outline: 大纲信息
            
        Returns:
            预测提示词
        """
        # 格式化候选列表：给 LLM 看的 candidate_id 用 1/2/3 短编号，避免长 UUID 出错
        candidates_text = "\n".join([
            f"候选 #{i+1}\n   候选编号 (candidate_id): {i+1}\n   标题: {c.get('title', '')}\n   套路: {c.get('method', '')}"
            for i, c in enumerate(top5)
        ])
        
        prompt = f"""【场景】
你现在正在刷订阅号信息流。"路人甲TM"今天有一篇新文章，你看到了下面这5个候选标题之一（每次只能看到1个，周围是其他10篇日常公众号文章）。

【候选标题】
{candidates_text}

【文章背景】（供你参考，但假装你只看标题）
- 选题方向: {topic.direction}
- 价值承诺: {topic.value_promise}

【你的任务】
逐个预测每个标题在你身上的点击意愿（0-10），并说明会点/不会点的原因。

评分标准:
- 9-10: 看到就点，完全无法抗拒
- 7-8: 很想点，大概率会打开
- 5-6: 有点兴趣，可能点可能不点
- 3-4: 兴趣不大，大概率划走
- 1-2: 看到就划，完全无感

【输出格式】
请严格按照以下JSON格式输出:
{{
  "predictions": [
    {{
      "candidate_id": "1",
      "click_willingness": 8,
      "click_reason": "反差感强 + 有具体数字 + 跟我的工作场景相关",
      "no_click_reason": "",
      "improvement_suggestion": "把'5个订阅'改成具体的服务名（如'5个SaaS'），更具体"
    }},
    {{
      "candidate_id": "1",
      "click_willingness": 4,
      "click_reason": "",
      "no_click_reason": "感觉是另一篇Claude教程，已经看过类似的",
      "improvement_suggestion": "需要叠加'反共识'或'数字冲击'修饰元素"
    }},
    ...
  ]
}}"""
        
        return prompt
    
    def _format_predictions(
        self,
        predictions: List[Dict[str, Any]],
        top5: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        格式化预测结果
        
        Args:
            predictions: 原始预测结果
            top5: Top 5候选列表
            
        Returns:
            格式化后的预测结果
        """
        # 三层鲁棒匹配 LLM 回填的 candidate_id（UUID / 短 ID / 位置）
        from app.services.title_generation.agent_b_reviewer import _robust_id_map
        pred_map = _robust_id_map(predictions, top5, key="candidate_id")
        unmatched = [i for i, c in enumerate(top5) if c.get("id", "") not in pred_map]
        if unmatched:
            logger.warning(
                f"Agent C: {len(unmatched)}/{len(top5)} 个候选未匹配到预测，"
                f"将使用默认 click_willingness=5（候选 #{[i+1 for i in unmatched]}）"
            )

        formatted = []
        for candidate in top5:
            real_id = candidate.get("id", "")
            pred = pred_map.get(real_id, {})
            formatted.append({
                "candidate_id": real_id,
                "title": candidate.get("title", ""),
                "click_willingness": pred.get("click_willingness", 5),
                "click_reason": pred.get("click_reason", ""),
                "no_click_reason": pred.get("no_click_reason", ""),
                "improvement_suggestion": pred.get("improvement_suggestion", ""),
            })
        
        return formatted
    
    def _calculate_average_click(self, predictions: List[Dict[str, Any]]) -> float:
        """
        计算平均点击意愿
        
        Args:
            predictions: 预测结果列表
            
        Returns:
            平均点击意愿
        """
        if not predictions:
            return 0.0
        
        total = sum(p.get("click_willingness", 0) for p in predictions)
        return round(total / len(predictions), 2)


# 导出
__all__ = ["ClickPredictorAgent"]

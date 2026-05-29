"""
Agent B - 标题评审员

角色定位: 公众号运营专家
核心任务: 一票否决扫描 + 6维度评分 + 筛选Top 5
"""

from typing import Dict, Any, List
import logging

from app.agents.base import BaseAgent
from app.schemas.title_generation import TopicInfo, OutlineInfo
from app.core.config import settings

logger = logging.getLogger(__name__)

# 6维度评分权重
SCORE_WEIGHTS = {
    "three_eyes": 0.25,  # 三个一眼达标度
    "emotion_trigger": 0.20,  # 情绪触发力度
    "specificity": 0.15,  # 具体性
    "length_compliance": 0.10,  # 长度合规
    "method_maturity": 0.15,  # 套路成熟度
    "outline_consistency": 0.15,  # 与大纲一致性
}

# 一票否决条件
VETO_CONDITIONS = [
    "含标题党词（震惊/速看/所有人都不知道等）",
    "涉及政治/监管敏感",
    "人身攻击具体个人/团队",
    "虚假承诺（包过/100%保证等）",
    "字数 < 10 或 > 22",
]


class TitleReviewerAgent(BaseAgent):
    """
    Agent B - 标题评审员
    
    角色: 公众号运营专家
    任务: 一票否决扫描 + 6维度评分 + 筛选Top 5
    """
    
    def __init__(self):
        """初始化标题评审员"""
        super().__init__()
        self.agent_name = "标题评审员"
        self.agent_role = "公众号运营专家"
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行标题评审任务
        
        Args:
            candidates: 候选标题列表
            topic: 选题信息
            outline: 大纲信息
            
        Returns:
            评审结果
        """
        candidates = kwargs.get("candidates", [])
        topic = kwargs.get("topic")
        outline = kwargs.get("outline")
        
        return await self.review_titles(candidates, topic, outline)
    
    async def review_titles(
        self,
        candidates: List[Dict[str, Any]],
        topic: TopicInfo,
        outline: OutlineInfo,
    ) -> Dict[str, Any]:
        """
        为每个候选标题生成「简介」（不再打分 / 不再淘汰 / 不再筛选 Top 5）。

        简介内容：这个标题/这篇文章大概写什么、为什么这么取（亮点角度）。

        Args:
            candidates: 候选标题列表
            topic: 选题信息
            outline: 大纲信息

        Returns:
            {"summaries": [{"candidate_id", "summary"}], "all": [...]}
        """
        logger.info(f"Agent B 开始生成标题简介，候选数量: {len(candidates)}")

        if not candidates:
            return {"summaries": [], "all": [], "covered_methods": 0}

        summaries = await self._generate_summaries(candidates, topic, outline)

        covered_methods = len(set(c.get("method", "") for c in candidates))
        logger.info(f"Agent B 简介生成完成，共 {len(summaries)} 条")

        return {
            "summaries": summaries,
            "all": candidates,
            "covered_methods": covered_methods,
        }

    async def _generate_summaries(
        self,
        candidates: List[Dict[str, Any]],
        topic: TopicInfo,
        outline: OutlineInfo,
    ) -> List[Dict[str, Any]]:
        """调用 AI 为每个候选生成简介"""
        prompt = self._build_summary_prompt(candidates, topic, outline)

        response = await self.call_ai_model(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.6,
        )

        result = self.parse_json_response(response)
        summary_map = {
            s.get("candidate_id") or s.get("id"): s.get("summary", "")
            for s in result.get("summaries", [])
        }

        summaries = []
        for c in candidates:
            cid = c.get("id", "")
            summaries.append({
                "candidate_id": cid,
                "summary": summary_map.get(cid, ""),
            })
        return summaries

    def _build_summary_prompt(
        self,
        candidates: List[Dict[str, Any]],
        topic: TopicInfo,
        outline: OutlineInfo,
    ) -> str:
        """构建简介生成提示词"""
        candidates_text = "\n".join([
            f"{i+1}. ID: {c.get('id', '')}\n   标题: {c.get('title', '')}\n   套路: {c.get('method', '')}\n   修饰元素: {', '.join(c.get('modifiers', []))}"
            for i, c in enumerate(candidates)
        ])

        return f"""【输入：候选标题】
{candidates_text}

【输入：选题 + 大纲】
选题:
- 标题: {topic.title}
- 方向: {topic.direction}
- 套路: {topic.method}
- 价值承诺: {topic.value_promise}

大纲:
- 各节小标题: {', '.join(outline.section_titles)}
- 关键信息点: {', '.join(outline.key_points)}

【你的任务】
为每个候选标题写一段「简介」（2-3 句话），说明：
1. 用这个标题，文章大概会写什么内容、给读者什么；
2. 这个标题为什么这么取——它的亮点/角度在哪（结合套路与选题）。
注意：不要打分、不要排序、不要淘汰，只写简介。

【输出格式】
请严格按照以下JSON格式输出:
{{
  "summaries": [
    {{
      "candidate_id": "候选ID",
      "summary": "这一段就是该标题的简介……"
    }}
  ]
}}"""
    
    def _veto_scan(
        self,
        candidates: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        一票否决扫描
        
        扫描候选，命中以下任一条件直接淘汰:
        - 含标题党词（震惊/速看/所有人都不知道等）
        - 政治/监管敏感
        - 人身攻击
        - 虚假承诺（包过/100%保证等）
        - 字数 < 10 或 > 22
        
        Args:
            candidates: 候选列表
            
        Returns:
            (被淘汰的候选, 存活的候选)
        """
        eliminated = []
        survived = []
        
        for candidate in candidates:
            title = candidate.get("title", "")
            word_count = candidate.get("word_count", len(title))
            
            # 检查字数
            if word_count < settings.MIN_TITLE_LENGTH or word_count > settings.MAX_TITLE_LENGTH:
                eliminated.append({
                    **candidate,
                    "elimination_reason": f"字数不符合要求: {word_count}字（要求{settings.MIN_TITLE_LENGTH}-{settings.MAX_TITLE_LENGTH}字）",
                })
                continue
            
            # 检查一票否决词
            veto_reason = self._check_veto_words(title)
            if veto_reason:
                eliminated.append({
                    **candidate,
                    "elimination_reason": veto_reason,
                })
                continue
            
            survived.append(candidate)
        
        return eliminated, survived
    
    def _check_veto_words(self, title: str) -> str:
        """
        检查一票否决词
        
        Args:
            title: 标题内容
            
        Returns:
            否决原因，如果没有否决词返回空字符串
        """
        # 标题党词
        clickbait_words = ["震惊", "速看", "所有人都不知道", "必看", "紧急通知"]
        for word in clickbait_words:
            if word in title:
                return f"含标题党词: '{word}'"
        
        # 虚假承诺
        false_promises = ["保证100%", "包过", "一定成功", "绝对有效"]
        for promise in false_promises:
            if promise in title:
                return f"虚假承诺: '{promise}'"
        
        # 政治敏感词（简化版）
        political_words = ["政府", "政治", "敏感词1", "敏感词2"]
        for word in political_words:
            if word in title:
                return f"政治敏感词: '{word}'"
        
        return ""
    
    async def _score_candidates(
        self,
        candidates: List[Dict[str, Any]],
        topic: TopicInfo,
        outline: OutlineInfo,
    ) -> List[Dict[str, Any]]:
        """
        对候选进行6维度评分
        
        维度:
        1. 三个一眼达标度 (25%)
        2. 情绪触发力度 (20%)
        3. 具体性 (15%)
        4. 长度合规 (10%)
        5. 套路成熟度 (15%)
        6. 与大纲一致性 (15%)
        
        Args:
            candidates: 候选列表
            topic: 选题信息
            outline: 大纲信息
            
        Returns:
            带评分的候选列表
        """
        # 构建评分提示词
        prompt = self._build_scoring_prompt(candidates, topic, outline)
        
        # 调用AI模型
        response = await self.call_ai_model(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.3,  # 低温度确保评分一致性
        )
        
        # 解析响应
        result = self.parse_json_response(response)
        
        # 合并评分结果
        scored_candidates = []
        scores_map = {s.get("candidate_id"): s for s in result.get("scores", [])}
        
        for candidate in candidates:
            candidate_id = candidate.get("id", "")
            score_data = scores_map.get(candidate_id, {})
            
            # 计算加权总分
            b_score = self._calculate_weighted_score(score_data)
            
            scored_candidates.append({
                **candidate,
                "b_score": b_score,
                "b_score_details": {
                    "three_eyes": score_data.get("three_eyes", 5),
                    "emotion_trigger": score_data.get("emotion_trigger", 5),
                    "specificity": score_data.get("specificity", 5),
                    "length_compliance": score_data.get("length_compliance", 5),
                    "method_maturity": score_data.get("method_maturity", 5),
                    "outline_consistency": score_data.get("outline_consistency", 5),
                },
                "scoring_explanation": score_data.get("explanation", ""),
            })
        
        return scored_candidates
    
    def _calculate_weighted_score(self, score_data: Dict[str, Any]) -> float:
        """
        计算加权总分
        
        B评分总分 = 0.25×一眼 + 0.20×情绪 + 0.15×具体性 + 0.10×长度 + 0.15×套路 + 0.15×大纲一致
        
        Args:
            score_data: 评分数据
            
        Returns:
            加权总分
        """
        total = 0.0
        
        for dimension, weight in SCORE_WEIGHTS.items():
            score = score_data.get(dimension, 5)
            total += score * weight
        
        return round(total, 2)
    
    def _select_top5(
        self,
        scored_candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        筛选Top 5
        
        按加权总分降序，输出Top 5候选。
        
        Args:
            scored_candidates: 带评分的候选列表
            
        Returns:
            Top 5候选列表
        """
        # 按分数降序排序
        sorted_candidates = sorted(
            scored_candidates,
            key=lambda x: x.get("b_score", 0),
            reverse=True,
        )
        
        # 取前5个
        top5 = sorted_candidates[:5]
        
        return top5
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一位运营过百万粉公众号的资深运营专家。

你的核心能力：
1. 从一堆候选中识别"哪些是真正有打开潜力的"
2. 精通6维度评分体系
3. 能准确判断标题与大纲的一致性

你的评分原则：
- 严格遵循评分锚点
- 与大纲一致性是硬约束，不一致直接0分
- 避免个人偏好影响评分"""
    
    def _build_scoring_prompt(
        self,
        candidates: List[Dict[str, Any]],
        topic: TopicInfo,
        outline: OutlineInfo,
    ) -> str:
        """
        构建评分提示词
        
        Args:
            candidates: 候选列表
            topic: 选题信息
            outline: 大纲信息
            
        Returns:
            评分提示词
        """
        # 格式化候选列表
        candidates_text = "\n".join([
            f"{i+1}. ID: {c.get('id', '')}\n   标题: {c.get('title', '')}\n   套路: {c.get('method', '')}\n   修饰元素: {', '.join(c.get('modifiers', []))}"
            for i, c in enumerate(candidates)
        ])
        
        prompt = f"""【输入：候选标题】
{candidates_text}

【输入：选题 + 大纲】
选题:
- 标题: {topic.title}
- 方向: {topic.direction}
- 套路: {topic.method}
- 价值承诺: {topic.value_promise}

大纲:
- 各节小标题: {', '.join(outline.section_titles)}
- 关键信息点: {', '.join(outline.key_points)}

【你的任务】
对每个候选进行6维度评分:

维度说明:
1. 三个一眼达标度 (25%): 1秒内看出"讲什么"、"对我有什么用"、"跟我什么关系"
   - 9-10: 三个一眼全到位
   - 7-8: 达成2个，第3个隐含
   - 4-6: 只达成1个
   - 1-3: 三个一眼都模糊

2. 情绪触发力度 (20%): 焦虑/好奇/共鸣/装逼/反差
   - 9-10: 强烈触发2个以上情绪
   - 7-8: 明确触发1个情绪
   - 4-6: 弱触发1个情绪
   - 1-3: 无明显情绪触发

3. 具体性 (15%): 数字/工具名/身份/场景
   - 9-10: 含3个及以上具体元素
   - 7-8: 含2个具体元素
   - 4-6: 含1个具体元素
   - 1-3: 无具体元素

4. 长度合规 (10%):
   - 10: 14-20字
   - 8: 10-13字
   - 6: 21-22字
   - 1: <10字或>22字

5. 套路成熟度 (15%):
   - 9-10: 命中高爆款模式，使用准确
   - 7-8: 命中套路，使用基本到位
   - 4-6: 命中套路但生硬
   - 1-3: 不属于已知套路

6. 与大纲一致性 (15%):
   - 9-10: 标题承诺被大纲完美兑现
   - 7-8: 标题承诺被大纲兑现，但对应弱化
   - 4-6: 标题承诺被大纲部分兑现
   - 1-3: 标题与大纲明显脱节
   - 0: 标题承诺无法被大纲兑现

【输出格式】
请严格按照以下JSON格式输出:
{{
  "scores": [
    {{
      "candidate_id": "候选ID",
      "three_eyes": 8,
      "emotion_trigger": 7,
      "specificity": 9,
      "length_compliance": 10,
      "method_maturity": 8,
      "outline_consistency": 9,
      "explanation": "评分说明"
    }},
    ...
  ]
}}"""
        
        return prompt


# 导出
__all__ = ["TitleReviewerAgent"]

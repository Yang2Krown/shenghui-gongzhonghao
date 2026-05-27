"""
Agent B - 标题评审员

角色定位: 公众号运营专家
核心任务: 一票否决扫描 + 6维度评分 + 筛选Top 5
"""

from typing import Dict, Any, List
import logging
from pathlib import Path

from app.services.title_generation.base import BaseAgent
from app.schemas.title_generation import TopicInfo, OutlineInfo
from app.core.config import settings

logger = logging.getLogger(__name__)


def _robust_id_map(items: List[Dict[str, Any]], candidates: List[Dict[str, Any]], *, key: str = "candidate_id") -> Dict[str, Dict[str, Any]]:
    """把 LLM 返回的 list（B 的 scores / C 的 predictions）按 candidate.id 索引。

    三层兜底匹配，从精确到模糊：
    1. 精确：LLM 回填的就是真 UUID
    2. 短 ID：LLM 回填的是 "1" / "2" / "3"（我们 prompt 里用的就是这种）
    3. 按位置：count 一致时按下标对应（LLM 完全没填 ID 也能救回）
    """
    if not items or not candidates:
        return {}

    out: Dict[str, Dict[str, Any]] = {}

    # 1. 位置兜底（最先填，被后两步覆盖）
    if len(items) == len(candidates):
        for i, item in enumerate(items):
            out[candidates[i]["id"]] = item

    # 2. 短 ID（"1" / "2" ... 或纯数字）
    for item in items:
        sid = str(item.get(key, "")).strip()
        try:
            idx = int(sid) - 1
            if 0 <= idx < len(candidates):
                out[candidates[idx]["id"]] = item
        except (ValueError, TypeError):
            pass

    # 3. 精确 UUID（最优先，覆盖前两步）
    cand_ids = {c.get("id") for c in candidates}
    for item in items:
        cid = item.get(key, "")
        if cid in cand_ids:
            out[cid] = item

    return out

# 获取当前文件所在目录
CURRENT_DIR = Path(__file__).parent

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
        评审标题候选
        
        执行4步流程:
        1. 一票否决扫描
        2. 6维度评分
        3. 与大纲一致性交叉验证
        4. 筛选Top 5
        
        Args:
            candidates: 候选标题列表
            topic: 选题信息
            outline: 大纲信息
            
        Returns:
            评审结果
        """
        logger.info(f"Agent B 开始评审，候选数量: {len(candidates)}")
        
        # Step 1: 一票否决扫描
        eliminated, survived = self._veto_scan(candidates)
        logger.info(f"一票否决扫描: 淘汰 {len(eliminated)} 个，存活 {len(survived)} 个")
        
        if not survived:
            logger.error("所有候选都被一票否决")
            return {
                "eliminated": eliminated,
                "scores": [],
                "top5": [],
                "top5_ids": [],
                "covered_methods": 0,
                "eliminated_count": len(eliminated),
            }
        
        # Step 2 & 3: 6维度评分 + 大纲一致性验证
        scored_candidates = await self._score_candidates(survived, topic, outline)
        
        # Step 4: 筛选Top 5
        top5 = self._select_top5(scored_candidates)
        
        # 统计信息
        covered_methods = len(set(c.get("method", "") for c in candidates))
        
        logger.info(f"Agent B 评审完成，Top 5: {[c.get('title', '')[:20] for c in top5]}")
        
        return {
            "eliminated": eliminated,
            "scores": scored_candidates,
            "top5": top5,
            "top5_ids": [c.get("id") for c in top5],
            "covered_methods": covered_methods,
            "eliminated_count": len(eliminated),
        }
    
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

        Schema 校验失败时自动重试，最多 3 次。

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
        MAX_RETRIES = 3
        prompt = self._build_scoring_prompt(candidates, topic, outline)
        system_prompt = self._get_system_prompt()

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            extra_hint = ""
            if attempt > 1:
                extra_hint = (
                    "\n\n【重要】上一次输出格式不符合要求。"
                    "请严格输出 JSON，必须包含 scores 数组，每个元素含 candidate_id、"
                    "three_eyes、emotion_trigger、specificity、length_compliance、"
                    "method_maturity、outline_consistency、explanation 字段。"
                    "不要输出任何 markdown 标记或解释文字。"
                )

            response = await self.call_ai_model(
                prompt=prompt,
                system_prompt=system_prompt + extra_hint,
                temperature=0.3,
                json_mode=True,
            )

            result = self.parse_json_response(response)

            logger.info(
                f"[Agent B 诊断] 第 {attempt}/{MAX_RETRIES} 次 LLM 原始响应前 400 字: {(response or '')[:400]!r}"
            )
            logger.info(
                f"[Agent B 诊断] parse_json_response 结果顶层 keys: {list(result.keys())}; "
                f"scores 数量: {len(result.get('scores', []) or [])}"
            )

            raw_scores = result.get("scores", []) or []
            if not raw_scores:
                last_error = ValueError("Agent B 输出格式不符合 schema: scores 为空")
                logger.warning(f"Agent B 第 {attempt}/{MAX_RETRIES} 次输出无 scores 数据")
                continue

            first_score = raw_scores[0] if raw_scores else {}
            logger.info(f"[Agent B 诊断] 第一条 score: {first_score}")

            scored_candidates = []
            scores_map = _robust_id_map(raw_scores, candidates, key="candidate_id")
            unmatched = [i for i, c in enumerate(candidates) if c.get("id", "") not in scores_map]
            logger.info(
                f"[Agent B 诊断] 匹配上 {len(candidates) - len(unmatched)}/{len(candidates)} 个候选"
            )
            if unmatched:
                logger.warning(
                    f"Agent B: {len(unmatched)}/{len(candidates)} 个候选未匹配到评分，"
                    f"将使用默认分 5（候选 #{[i+1 for i in unmatched]}）"
                )

            for candidate in candidates:
                candidate_id = candidate.get("id", "")
                score_data = scores_map.get(candidate_id, {})
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

        logger.error(f"[Agent B] {MAX_RETRIES} 次尝试均失败")
        raise last_error
    
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
        prompt_file = CURRENT_DIR / "prompts" / "agent_b_system.txt"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
        # 回退到硬编码版本
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
        # 格式化候选列表：给 LLM 看的 candidate_id 直接用 1/2/3 短编号，
        # 避免它在长 UUID 上截断 / 拼错导致回填的 scores 对不上
        candidates_text = "\n".join([
            f"候选 #{i+1}\n   候选编号 (candidate_id): {i+1}\n   标题: {c.get('title', '')}\n   套路: {c.get('method', '')}\n   修饰元素: {', '.join(c.get('modifiers', []))}"
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
      "candidate_id": "1",
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

"""
Agent A - 标题创作员

角色定位: 百万粉 AI 公众号博主
核心任务: 基于选题和大纲生成10-15个标题候选，覆盖至少6种套路
"""

from typing import Dict, Any, List, Optional
import logging

from app.agents.base import BaseAgent
from app.schemas.title_generation import TopicInfo, OutlineInfo
from app.core.config import settings

logger = logging.getLogger(__name__)

# 标题套路库（简化版，完整版从文件加载）
TITLE_METHODS = {
    "痛点直击型": {
        "description": "精准戳中读者一个真实的痛，然后承诺解决方案",
        "templates": [
            "[痛点描述]？这个 [工具/方法] 彻底解决了",
            "[痛点]，我用 [方案] 终于搞定了",
        ],
        "applicable_directions": ["解决问题型", "实践型", "教程型"],
    },
    "数字冲击型": {
        "description": "用具体数字制造可信度和冲击感",
        "templates": [
            "[数字] + [动作] + [成果]",
            "我用 [时间/金钱] 完成了 [意外成果]",
        ],
        "applicable_directions": ["实践型", "解决问题型", "资讯型"],
    },
    "第一人称故事型": {
        "description": "用'我'作为主语，把内容包装成一个故事",
        "templates": [
            "我用 [工具] 做了 [意外的事]",
            "我和 [对象]，用 [工具] 做了一件 [形容词] 的事",
        ],
        "applicable_directions": ["实践型", "整活型", "解决问题型"],
    },
    "反差反转型": {
        "description": "制造预期和现实的落差，激发好奇心",
        "templates": [
            "我以为 X，结果 Y",
            "本以为 [小事]，没想到 [大事]",
        ],
        "applicable_directions": ["实践型", "观点型", "解决问题型"],
    },
    "反共识型": {
        "description": "唱反调，激发读者'独立思考'的认同感",
        "templates": [
            "所有人都在吹 X，但我说 Y",
            "为什么我说 [被普遍认同的事] 是错的",
        ],
        "applicable_directions": ["观点型"],
    },
    "焦虑制造型": {
        "description": "触发读者对职业/行业的担忧",
        "templates": [
            "[职业/行业] 要变天了",
            "[X] 出来后，[职业/工具] 不复存在",
        ],
        "applicable_directions": ["观点型", "资讯型"],
    },
    "实用清单型": {
        "description": "明确告诉读者'这里有 N 个实用的东西可以收藏'",
        "templates": [
            "[X] 的 [N] 个用法 / 技巧 / 模板",
            "[场景] 必看的 [N] 个 [东西]",
        ],
        "applicable_directions": ["教程型", "解决问题型", "实践型"],
    },
    "对比测评型": {
        "description": "A vs B，替读者做决策",
        "templates": [
            "[A] vs [B]，[N] 个真实任务实测",
            "[A] 和 [B] 我都用了 [时间]，结论是这样",
        ],
        "applicable_directions": ["观点型", "实践型"],
    },
    "悬念钩子型": {
        "description": "留白，说一半藏一半，激发读者点开揭秘的欲望",
        "templates": [
            "[X]，可能会改变你对 [Y] 的看法",
            "[人/事] 背后，藏着一个 [大秘密]",
        ],
        "applicable_directions": ["观点型", "资讯型"],
    },
    "时间紧迫型": {
        "description": "用时间制造稀缺感、新鲜感",
        "templates": [
            "刚刚 [事件]",
            "[N] 小时前 [事件]",
        ],
        "applicable_directions": ["资讯型"],
    },
    "身份代入型": {
        "description": "明确点名特定身份，让目标读者觉得'这就是给我看的'",
        "templates": [
            "[身份] 必看：[内容]",
            "[身份] 专属的 [工具/方法]",
        ],
        "applicable_directions": ["解决问题型", "实践型", "教程型"],
    },
    "反向推荐型": {
        "description": "'劝退'现有选项，推荐新选项",
        "templates": [
            "别用 [X] 了，试试 [Y]",
            "[X] 已经不推荐了，现在用 [Y]",
        ],
        "applicable_directions": ["观点型", "解决问题型"],
    },
}

# 修饰元素
MODIFIERS = {
    "数字": "具体的数字（3、5、7等奇数更佳）",
    "身份代入词": "'我'、'我们'、'产品经理'等身份词",
    "反差/反预期词": "'居然'、'竟然'、'没想到'、'意外'等",
    "紧迫/时效词": "'刚刚'、'今天'、'昨晚'等时间词",
    "情绪词": "'崩溃'、'心疼'、'离谱'、'神技'等",
    "反常识词": "'其实'、'真相'、'真正的'等",
}

# 反模式（一票否决项）
ANTI_PATTERNS = [
    "震惊", "速看", "所有人都不知道",
    "政治敏感词", "人身攻击", "虚假承诺（包过/保证100%）",
]


class TitleCreatorAgent(BaseAgent):
    """
    Agent A - 标题创作员
    
    角色: 百万粉 AI 公众号博主
    任务: 生成10-15个标题候选，覆盖至少6种套路
    """
    
    def __init__(self):
        """初始化标题创作员"""
        super().__init__()
        self.agent_name = "标题创作员"
        self.agent_role = "百万粉 AI 公众号博主"
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行标题生成任务
        
        Args:
            topic: 选题信息
            outline: 大纲信息
            feedback: 重生反馈（可选）
            
        Returns:
            包含候选标题列表的字典
        """
        topic = kwargs.get("topic")
        outline = kwargs.get("outline")
        feedback = kwargs.get("feedback")
        
        return await self.generate_titles(topic, outline, feedback)
    
    async def generate_titles(
        self,
        topic: TopicInfo,
        outline: OutlineInfo,
        feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        生成标题候选
        
        Args:
            topic: 选题信息
            outline: 大纲信息
            feedback: 重生反馈（可选）
            
        Returns:
            包含候选标题列表的字典
        """
        logger.info(f"Agent A 开始生成标题，选题: {topic.title}")
        
        # 构建提示词
        prompt = self._build_prompt(topic, outline, feedback)
        
        # 调用AI模型
        response = await self.call_ai_model(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.8,  # 稍高温度增加创造性
        )
        
        # 解析响应
        result = self.parse_json_response(response)
        
        # 验证和后处理
        candidates = self._validate_candidates(result.get("candidates", []))
        
        logger.info(f"Agent A 生成了 {len(candidates)} 个候选标题")
        
        return {
            "candidates": candidates,
            "raw_response": response,
        }
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一位百万粉的 AI 公众号博主，深谙公众号读者打开决策机制。

你的核心能力：
1. 从一条选题+大纲里生成多角度、多套路的标题候选
2. 精通12种标题套路和6类修饰元素
3. 每个标题都必须让读者在1秒内完成"三个一眼"判断

你的工作原则：
- 打开率优先于正确性
- 多候选 + 多套路 > 单候选反复打磨
- 标题必须兑现承诺
- 避免一票否决词"""
    
    def _build_prompt(
        self,
        topic: TopicInfo,
        outline: OutlineInfo,
        feedback: Optional[str] = None,
    ) -> str:
        """
        构建提示词
        
        Args:
            topic: 选题信息
            outline: 大纲信息
            feedback: 重生反馈
            
        Returns:
            完整的提示词
        """
        # 选择优先套路
        priority_methods = self._get_priority_methods(topic.direction)
        
        prompt = f"""【输入】
选题:
- 标题（草标题）: {topic.title}
- 方向: {topic.direction}
- 套路（选题套路）: {topic.method}
- 价值承诺: {topic.value_promise}

最终大纲:
- 各节小标题: {', '.join(outline.section_titles)}
- 关键信息点: {', '.join(outline.key_points)}
- 传播标签分布: {', '.join(outline.spread_tags) if outline.spread_tags else '无'}

【参考资产】
标题套路库（12种套路）:
{self._format_methods()}

修饰元素（6类）:
{self._format_modifiers()}

该方向的优先套路: {', '.join(priority_methods)}

反模式（一票否决项）:
{', '.join(ANTI_PATTERNS)}

【你的任务】
产出 {settings.MIN_CANDIDATES}-{settings.MAX_CANDIDATES} 个标题候选，每个候选必须标注使用的套路和修饰元素。

【硬约束】
1. 候选数量 {settings.MIN_CANDIDATES}-{settings.MAX_CANDIDATES} 个
2. 必须覆盖至少 {settings.MIN_COVERAGE_METHODS} 种不同套路
3. 单一套路不超过 {settings.MAX_SAME_METHOD} 个候选
4. 优先使用该方向的优先套路（占比 ≥ {settings.PRIORITY_METHOD_RATIO * 100}%）
5. 每个标题字数 {settings.OPTIMAL_MIN_LENGTH}-{settings.OPTIMAL_MAX_LENGTH} 为最佳（{settings.MIN_TITLE_LENGTH}-{settings.OPTIMAL_MIN_LENGTH - 1} 或 {settings.OPTIMAL_MAX_LENGTH + 1}-{settings.MAX_TITLE_LENGTH} 允许但减分）
6. 不允许标题党词、敏感内容、虚假承诺
7. 文字必须真实差异，不允许"换一个字"的伪候选

【自检清单】
□ 候选数量是否在 {settings.MIN_CANDIDATES}-{settings.MAX_CANDIDATES}？
□ 是否覆盖至少 {settings.MIN_COVERAGE_METHODS} 种套路？
□ 单套路是否未超过 {settings.MAX_SAME_METHOD} 个？
□ 优先套路占比是否 ≥ {settings.PRIORITY_METHOD_RATIO * 100}%？
□ 字数是否都在 {settings.MIN_TITLE_LENGTH}-{settings.MAX_TITLE_LENGTH}？
□ 是否避免了一票否决词？
□ 每个候选是否真实差异？"""
        
        # 添加重生反馈
        if feedback:
            prompt += f"""

【第二次调用，前次失败原因】
{feedback}

【请针对性改进】
针对上述问题重新生成 {settings.MIN_CANDIDATES}-{settings.MAX_CANDIDATES} 个候选，但仍要保持套路覆盖度。"""
        
        prompt += """

【输出格式】
请严格按照以下JSON格式输出:
{
  "candidates": [
    {
      "title": "标题内容",
      "word_count": 20,
      "method": "套路名称",
      "modifiers": ["修饰元素1", "修饰元素2"],
      "explanation": "为什么这样写"
    },
    ...
  ]
}"""
        
        return prompt
    
    def _format_methods(self) -> str:
        """格式化套路信息"""
        lines = []
        for name, info in TITLE_METHODS.items():
            lines.append(f"- {name}: {info['description']}")
        return "\n".join(lines)
    
    def _format_modifiers(self) -> str:
        """格式化修饰元素信息"""
        lines = []
        for name, desc in MODIFIERS.items():
            lines.append(f"- {name}: {desc}")
        return "\n".join(lines)
    
    def _get_priority_methods(self, direction: str) -> List[str]:
        """
        获取该方向的优先套路
        
        Args:
            direction: 内容方向
            
        Returns:
            优先套路列表
        """
        priority_methods = []
        for method_name, method_info in TITLE_METHODS.items():
            if direction in method_info["applicable_directions"]:
                priority_methods.append(method_name)
        
        return priority_methods if priority_methods else list(TITLE_METHODS.keys())[:6]
    
    def _validate_candidates(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        验证和后处理候选标题
        
        Args:
            candidates: 原始候选列表
            
        Returns:
            验证后的候选列表
        """
        validated = []
        
        for candidate in candidates:
            title = candidate.get("title", "")
            
            # 检查字数
            word_count = len(title)
            if word_count < settings.MIN_TITLE_LENGTH or word_count > settings.MAX_TITLE_LENGTH:
                logger.warning(f"标题字数不符合要求: {title} ({word_count}字)")
                continue
            
            # 检查一票否决词
            if self._contains_anti_pattern(title):
                logger.warning(f"标题包含一票否决词: {title}")
                continue
            
            # 更新字数
            candidate["word_count"] = word_count
            
            # 验证套路
            method = candidate.get("method", "")
            if method not in TITLE_METHODS:
                # 尝试模糊匹配
                for valid_method in TITLE_METHODS.keys():
                    if valid_method in method or method in valid_method:
                        candidate["method"] = valid_method
                        break
                else:
                    # 默认使用第一个套路
                    candidate["method"] = list(TITLE_METHODS.keys())[0]
            
            # 验证修饰元素
            modifiers = candidate.get("modifiers", [])
            if not isinstance(modifiers, list):
                modifiers = []
            candidate["modifiers"] = modifiers[:settings.MAX_MODIFIERS_PER_TITLE]
            
            validated.append(candidate)
        
        return validated
    
    def _contains_anti_pattern(self, title: str) -> bool:
        """
        检查标题是否包含一票否决词
        
        Args:
            title: 标题内容
            
        Returns:
            是否包含一票否决词
        """
        anti_patterns = ["震惊", "速看", "所有人都不知道", "保证100%", "包过"]
        
        for pattern in anti_patterns:
            if pattern in title:
                return True
        
        return False


# 导出
__all__ = ["TitleCreatorAgent"]

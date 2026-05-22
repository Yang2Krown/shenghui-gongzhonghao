"""
AI服务模块
提供多AI模型支持的服务层
"""
import logging
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod

from app.core.config import settings

logger = logging.getLogger(__name__)


class BaseAIService(ABC):
    """AI服务基类"""

    def __init__(self, provider: str, model_name: str, api_key: str, api_base: str):
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key
        self.api_base = api_base
        self.logger = logging.getLogger(f"{self.__class__.__name__}.{provider}")

    @abstractmethod
    async def generate_content(self, prompt: str, style: Optional[Dict[str, Any]] = None) -> str:
        """生成内容"""
        pass

    @abstractmethod
    async def analyze_style(self, articles: List[str]) -> Dict[str, Any]:
        """分析写作风格"""
        pass

    @abstractmethod
    async def summarize_content(self, content: str) -> str:
        """内容摘要"""
        pass

    @abstractmethod
    async def suggest_titles(self, content: str, count: int = 5) -> List[str]:
        """标题建议"""
        pass

    @abstractmethod
    async def optimize_content(
        self,
        content: str,
        style: Optional[Dict[str, Any]] = None,
        optimization_type: str = "general"
    ) -> str:
        """优化内容"""
        pass

    @abstractmethod
    async def apply_style_to_content(self, content: str, style: Dict[str, Any]) -> str:
        """应用风格到内容"""
        pass


class OpenAIService(BaseAIService):
    """OpenAI服务"""

    def __init__(self):
        super().__init__(
            provider="openai",
            model_name=settings.DEFAULT_AI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            api_base=settings.OPENAI_API_BASE
        )

    async def generate_content(self, prompt: str, style: Optional[Dict[str, Any]] = None) -> str:
        """生成内容"""
        try:
            import openai
            
            client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
            
            messages = [
                {"role": "system", "content": "你是一位专业的公众号内容创作者。"},
                {"role": "user", "content": prompt}
            ]
            
            if style:
                style_instruction = self._build_style_instruction(style)
                messages.insert(1, {"role": "system", "content": style_instruction})
            
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"OpenAI生成内容失败: {e}")
            raise

    async def analyze_style(self, articles: List[str]) -> Dict[str, Any]:
        """分析写作风格"""
        try:
            import openai
            
            client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
            
            # 合并文章内容
            combined_content = "\n\n---\n\n".join(articles[:5])  # 限制分析数量
            
            prompt = f"""请分析以下文章的写作风格，包括：
1. 语气特点（如：正式、轻松、幽默等）
2. 文章结构（如：总分总、递进等）
3. 常用词汇和表达方式
4. 段落长度和句式特点
5. 标题风格

文章内容：
{combined_content}

请以JSON格式返回分析结果。"""
            
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一位文学分析专家，擅长分析写作风格。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            # 解析响应
            import json
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            self.logger.error(f"OpenAI分析风格失败: {e}")
            # 返回默认风格
            return {
                "tone": "专业",
                "style": "简洁明了",
                "structure": "总分总",
                "vocabulary": ["科技", "创新", "发展"],
                "paragraph_length": "中等",
                "sentence_style": "多样化"
            }

    async def summarize_content(self, content: str) -> str:
        """内容摘要"""
        try:
            import openai
            
            client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
            
            prompt = f"请为以下内容生成一段简洁的摘要（100-200字）：\n\n{content}"
            
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一位内容摘要专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"OpenAI生成摘要失败: {e}")
            raise

    async def suggest_titles(self, content: str, count: int = 5) -> List[str]:
        """标题建议"""
        try:
            import openai
            
            client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
            
            prompt = f"请为以下内容生成{count}个吸引人的公众号标题，用JSON数组格式返回：\n\n{content[:1000]}"
            
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一位公众号标题创作专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            import json
            titles = json.loads(response.choices[0].message.content)
            return titles[:count]
            
        except Exception as e:
            self.logger.error(f"OpenAI生成标题失败: {e}")
            return [f"文章标题 {i+1}" for i in range(count)]

    async def optimize_content(
        self,
        content: str,
        style: Optional[Dict[str, Any]] = None,
        optimization_type: str = "general"
    ) -> str:
        """优化内容"""
        try:
            import openai
            
            client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
            
            optimization_prompts = {
                "general": "请优化以下文章，使其更流畅、更吸引人：",
                "readability": "请优化以下文章的可读性，使其更容易理解：",
                "engagement": "请优化以下文章，使其更具互动性和吸引力：",
                "professional": "请优化以下文章，使其更专业、更有深度："
            }
            
            base_prompt = optimization_prompts.get(optimization_type, optimization_prompts["general"])
            
            messages = [
                {"role": "system", "content": "你是一位专业的文章编辑。"},
                {"role": "user", "content": f"{base_prompt}\n\n{content}"}
            ]
            
            if style:
                style_instruction = self._build_style_instruction(style)
                messages.insert(1, {"role": "system", "content": style_instruction})
            
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.5,
                max_tokens=len(content) * 2
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"OpenAI优化内容失败: {e}")
            raise

    async def apply_style_to_content(self, content: str, style: Dict[str, Any]) -> str:
        """应用风格到内容"""
        try:
            import openai
            
            client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
            
            style_instruction = self._build_style_instruction(style)
            
            prompt = f"""请按照以下风格要求改写文章内容：

{style_instruction}

原始文章：
{content}

请保持文章的核心观点和信息，但完全按照上述风格要求进行改写。"""
            
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一位风格改写专家，能够准确模仿各种写作风格。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=len(content) * 2
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"OpenAI应用风格失败: {e}")
            raise

    def _build_style_instruction(self, style: Dict[str, Any]) -> str:
        """构建风格指令"""
        instructions = ["请按照以下写作风格进行创作："]
        
        if "tone" in style:
            instructions.append(f"- 语气：{style['tone']}")
        if "style" in style:
            instructions.append(f"- 风格：{style['style']}")
        if "structure" in style:
            instructions.append(f"- 结构：{style['structure']}")
        if "vocabulary" in style:
            vocab = ", ".join(style["vocabulary"][:10])
            instructions.append(f"- 常用词汇：{vocab}")
        if "paragraph_length" in style:
            instructions.append(f"- 段落长度：{style['paragraph_length']}")
        if "sentence_style" in style:
            instructions.append(f"- 句式特点：{style['sentence_style']}")
        
        return "\n".join(instructions)


class DeepSeekService(BaseAIService):
    """DeepSeek服务"""

    def __init__(self):
        super().__init__(
            provider="deepseek",
            model_name="deepseek-chat",
            api_key=settings.DEEPSEEK_API_KEY,
            api_base=settings.DEEPSEEK_API_BASE
        )

    async def generate_content(self, prompt: str, style: Optional[Dict[str, Any]] = None) -> str:
        """生成内容"""
        try:
            import openai
            
            client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
            
            messages = [
                {"role": "system", "content": "你是一位专业的公众号内容创作者。"},
                {"role": "user", "content": prompt}
            ]
            
            if style:
                style_instruction = self._build_style_instruction(style)
                messages.insert(1, {"role": "system", "content": style_instruction})
            
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"DeepSeek生成内容失败: {e}")
            raise

    async def analyze_style(self, articles: List[str]) -> Dict[str, Any]:
        """分析写作风格"""
        try:
            import openai
            
            client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
            
            combined_content = "\n\n---\n\n".join(articles[:5])
            
            prompt = f"""请分析以下文章的写作风格，包括：
1. 语气特点
2. 文章结构
3. 常用词汇和表达方式
4. 段落长度和句式特点
5. 标题风格

文章内容：
{combined_content}

请以JSON格式返回分析结果。"""
            
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一位文学分析专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            self.logger.error(f"DeepSeek分析风格失败: {e}")
            return {
                "tone": "专业",
                "style": "简洁明了",
                "structure": "总分总",
                "vocabulary": ["科技", "创新", "发展"],
                "paragraph_length": "中等",
                "sentence_style": "多样化"
            }

    async def summarize_content(self, content: str) -> str:
        """内容摘要"""
        try:
            import openai
            
            client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
            
            prompt = f"请为以下内容生成一段简洁的摘要（100-200字）：\n\n{content}"
            
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一位内容摘要专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"DeepSeek生成摘要失败: {e}")
            raise

    async def suggest_titles(self, content: str, count: int = 5) -> List[str]:
        """标题建议"""
        try:
            import openai
            
            client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
            
            prompt = f"请为以下内容生成{count}个吸引人的公众号标题，用JSON数组格式返回：\n\n{content[:1000]}"
            
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一位公众号标题创作专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            import json
            titles = json.loads(response.choices[0].message.content)
            return titles[:count]
            
        except Exception as e:
            self.logger.error(f"DeepSeek生成标题失败: {e}")
            return [f"文章标题 {i+1}" for i in range(count)]

    async def optimize_content(
        self,
        content: str,
        style: Optional[Dict[str, Any]] = None,
        optimization_type: str = "general"
    ) -> str:
        """优化内容"""
        try:
            import openai
            
            client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
            
            optimization_prompts = {
                "general": "请优化以下文章，使其更流畅、更吸引人：",
                "readability": "请优化以下文章的可读性：",
                "engagement": "请优化以下文章的互动性：",
                "professional": "请优化以下文章的专业性："
            }
            
            base_prompt = optimization_prompts.get(optimization_type, optimization_prompts["general"])
            
            messages = [
                {"role": "system", "content": "你是一位专业的文章编辑。"},
                {"role": "user", "content": f"{base_prompt}\n\n{content}"}
            ]
            
            if style:
                style_instruction = self._build_style_instruction(style)
                messages.insert(1, {"role": "system", "content": style_instruction})
            
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.5,
                max_tokens=len(content) * 2
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"DeepSeek优化内容失败: {e}")
            raise

    async def apply_style_to_content(self, content: str, style: Dict[str, Any]) -> str:
        """应用风格到内容"""
        try:
            import openai
            
            client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
            
            style_instruction = self._build_style_instruction(style)
            
            prompt = f"""请按照以下风格要求改写文章内容：

{style_instruction}

原始文章：
{content}

请保持文章的核心观点和信息，但完全按照上述风格要求进行改写。"""
            
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一位风格改写专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=len(content) * 2
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"DeepSeek应用风格失败: {e}")
            raise

    def _build_style_instruction(self, style: Dict[str, Any]) -> str:
        """构建风格指令"""
        instructions = ["请按照以下写作风格进行创作："]
        
        if "tone" in style:
            instructions.append(f"- 语气：{style['tone']}")
        if "style" in style:
            instructions.append(f"- 风格：{style['style']}")
        if "structure" in style:
            instructions.append(f"- 结构：{style['structure']}")
        if "vocabulary" in style:
            vocab = ", ".join(style["vocabulary"][:10])
            instructions.append(f"- 常用词汇：{vocab}")
        
        return "\n".join(instructions)


class TongyiService(BaseAIService):
    """通义千问服务"""

    def __init__(self):
        super().__init__(
            provider="tongyi",
            model_name="qwen-turbo",
            api_key=settings.TONGYI_API_KEY,
            api_base=settings.TONGYI_API_BASE
        )

    async def generate_content(self, prompt: str, style: Optional[Dict[str, Any]] = None) -> str:
        """生成内容"""
        try:
            import httpx
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            messages = [
                {"role": "system", "content": "你是一位专业的公众号内容创作者。"},
                {"role": "user", "content": prompt}
            ]
            
            if style:
                style_instruction = self._build_style_instruction(style)
                messages.insert(1, {"role": "system", "content": style_instruction})
            
            payload = {
                "model": self.model_name,
                "input": {
                    "messages": messages
                },
                "parameters": {
                    "temperature": 0.7,
                    "max_tokens": 2000
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/services/aigc/text-generation/generation",
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                return result["output"]["choices"][0]["message"]["content"]
            
        except Exception as e:
            self.logger.error(f"通义千问生成内容失败: {e}")
            raise

    async def analyze_style(self, articles: List[str]) -> Dict[str, Any]:
        """分析写作风格"""
        try:
            import httpx
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            combined_content = "\n\n---\n\n".join(articles[:5])
            
            prompt = f"""请分析以下文章的写作风格，包括：
1. 语气特点
2. 文章结构
3. 常用词汇和表达方式
4. 段落长度和句式特点
5. 标题风格

文章内容：
{combined_content}

请以JSON格式返回分析结果。"""
            
            payload = {
                "model": self.model_name,
                "input": {
                    "messages": [
                        {"role": "system", "content": "你是一位文学分析专家。"},
                        {"role": "user", "content": prompt}
                    ]
                },
                "parameters": {
                    "temperature": 0.3,
                    "max_tokens": 1000
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/services/aigc/text-generation/generation",
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                
                import json
                return json.loads(result["output"]["choices"][0]["message"]["content"])
            
        except Exception as e:
            self.logger.error(f"通义千问分析风格失败: {e}")
            return {
                "tone": "专业",
                "style": "简洁明了",
                "structure": "总分总",
                "vocabulary": ["科技", "创新", "发展"],
                "paragraph_length": "中等",
                "sentence_style": "多样化"
            }

    async def summarize_content(self, content: str) -> str:
        """内容摘要"""
        try:
            import httpx
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            prompt = f"请为以下内容生成一段简洁的摘要（100-200字）：\n\n{content}"
            
            payload = {
                "model": self.model_name,
                "input": {
                    "messages": [
                        {"role": "system", "content": "你是一位内容摘要专家。"},
                        {"role": "user", "content": prompt}
                    ]
                },
                "parameters": {
                    "temperature": 0.3,
                    "max_tokens": 500
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/services/aigc/text-generation/generation",
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                return result["output"]["choices"][0]["message"]["content"]
            
        except Exception as e:
            self.logger.error(f"通义千问生成摘要失败: {e}")
            raise

    async def suggest_titles(self, content: str, count: int = 5) -> List[str]:
        """标题建议"""
        try:
            import httpx
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            prompt = f"请为以下内容生成{count}个吸引人的公众号标题，用JSON数组格式返回：\n\n{content[:1000]}"
            
            payload = {
                "model": self.model_name,
                "input": {
                    "messages": [
                        {"role": "system", "content": "你是一位公众号标题创作专家。"},
                        {"role": "user", "content": prompt}
                    ]
                },
                "parameters": {
                    "temperature": 0.7,
                    "max_tokens": 500
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/services/aigc/text-generation/generation",
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                
                import json
                titles = json.loads(result["output"]["choices"][0]["message"]["content"])
                return titles[:count]
            
        except Exception as e:
            self.logger.error(f"通义千问生成标题失败: {e}")
            return [f"文章标题 {i+1}" for i in range(count)]

    async def optimize_content(
        self,
        content: str,
        style: Optional[Dict[str, Any]] = None,
        optimization_type: str = "general"
    ) -> str:
        """优化内容"""
        try:
            import httpx
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            optimization_prompts = {
                "general": "请优化以下文章，使其更流畅、更吸引人：",
                "readability": "请优化以下文章的可读性：",
                "engagement": "请优化以下文章的互动性：",
                "professional": "请优化以下文章的专业性："
            }
            
            base_prompt = optimization_prompts.get(optimization_type, optimization_prompts["general"])
            
            messages = [
                {"role": "system", "content": "你是一位专业的文章编辑。"},
                {"role": "user", "content": f"{base_prompt}\n\n{content}"}
            ]
            
            if style:
                style_instruction = self._build_style_instruction(style)
                messages.insert(1, {"role": "system", "content": style_instruction})
            
            payload = {
                "model": self.model_name,
                "input": {
                    "messages": messages
                },
                "parameters": {
                    "temperature": 0.5,
                    "max_tokens": len(content) * 2
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/services/aigc/text-generation/generation",
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                return result["output"]["choices"][0]["message"]["content"]
            
        except Exception as e:
            self.logger.error(f"通义千问优化内容失败: {e}")
            raise

    async def apply_style_to_content(self, content: str, style: Dict[str, Any]) -> str:
        """应用风格到内容"""
        try:
            import httpx
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            style_instruction = self._build_style_instruction(style)
            
            prompt = f"""请按照以下风格要求改写文章内容：

{style_instruction}

原始文章：
{content}

请保持文章的核心观点和信息，但完全按照上述风格要求进行改写。"""
            
            payload = {
                "model": self.model_name,
                "input": {
                    "messages": [
                        {"role": "system", "content": "你是一位风格改写专家。"},
                        {"role": "user", "content": prompt}
                    ]
                },
                "parameters": {
                    "temperature": 0.5,
                    "max_tokens": len(content) * 2
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/services/aigc/text-generation/generation",
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                return result["output"]["choices"][0]["message"]["content"]
            
        except Exception as e:
            self.logger.error(f"通义千问应用风格失败: {e}")
            raise

    def _build_style_instruction(self, style: Dict[str, Any]) -> str:
        """构建风格指令"""
        instructions = ["请按照以下写作风格进行创作："]
        
        if "tone" in style:
            instructions.append(f"- 语气：{style['tone']}")
        if "style" in style:
            instructions.append(f"- 风格：{style['style']}")
        if "structure" in style:
            instructions.append(f"- 结构：{style['structure']}")
        if "vocabulary" in style:
            vocab = ", ".join(style["vocabulary"][:10])
            instructions.append(f"- 常用词汇：{vocab}")
        
        return "\n".join(instructions)


def get_ai_service(provider: Optional[str] = None) -> BaseAIService:
    """
    获取AI服务实例
    
    Args:
        provider: AI提供商，默认使用配置中的默认提供商
        
    Returns:
        AI服务实例
    """
    provider = provider or settings.DEFAULT_AI_PROVIDER
    
    services = {
        "openai": OpenAIService,
        "deepseek": DeepSeekService,
        "tongyi": TongyiService
    }
    
    service_class = services.get(provider)
    if not service_class:
        raise ValueError(f"不支持的AI提供商: {provider}")

    return service_class()


ai_service = get_ai_service()

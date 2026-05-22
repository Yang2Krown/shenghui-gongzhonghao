# 项目长期记忆

## 项目概述
公众号内容创作自动化系统，包含选题挖掘、大纲生成、标题生成、正文生成四大模块。

## 技术栈
- 后端：FastAPI + Celery + SQLAlchemy + PostgreSQL
- 前端：Vue 3 + Element Plus
- LLM：DeepSeek（默认）/ Anthropic Claude（可切换）
- 代理：127.0.0.1:7890

## 模块架构
1. **选题挖掘** (`services/topic_mining/`)：Agent A（衍生）→ Agent B（评分）
2. **大纲生成** (`services/outline_generation/`)：多 Agent 协作
3. **标题生成** (`services/title_generation_service.py`)：4 Agent 协作
4. **正文生成** (`services/content_generation/`)：4 Agent 协作（A→B→C→D）

## LLM 客户端
- 入口：`app.services.llm.get_llm_client()`
- 消息格式：`ChatMessage(role, content)`
- JSON 解析：`parse_json_loose(text)`
- JSON 模式：`json_mode=True`

## 用户偏好
- 中文用户，沟通极度简洁
- 直接提问，不提供额外背景
- 遇到错误会主动重试
- 偏好精炼输出，反感多余解释

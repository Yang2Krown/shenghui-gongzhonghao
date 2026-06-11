"""测试事实提取模块。

运行方式：
  cd backend && .venv/bin/python -m tests.test_source_extraction

测试内容：
  1. user_source_extractor — 从用户文本提取事实
  2. source_collector — 从数据库 RawInfo 提取事实（需要 DB）
"""

import asyncio
import sys
import os

# 确保 backend 目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_user_source_extractor():
    """测试用户文本事实提取。"""
    from app.services.user_source_extractor import extract_facts_from_user_text

    # 模拟一篇包含具体事实的文章
    test_text = """
    2025年6月，OpenAI 正式发布了 GPT-5 模型，参数量达到 2 万亿。
    该模型在 MMLU 基准测试中取得了 92.3% 的准确率，比 GPT-4 提升了 8 个百分点。
    OpenAI CEO Sam Altman 在发布会上表示，GPT-5 将首先向 ChatGPT Plus 用户开放，
    订阅价格维持每月 20 美元不变。企业版将在 2025 年第三季度推出。
    
    与此同时，Anthropic 的 Claude 4 也在同月发布，主打安全性和长文本处理能力。
    Claude 4 支持 500K token 的上下文窗口，是 GPT-5 的 5 倍。
    Anthropic CEO Dario Amodei 强调，Claude 4 在安全性测试中零越狱成功率。
    
    国内方面，DeepSeek 于 2025 年 5 月开源了 DeepSeek-V3 模型，
    在 HuggingFace 上获得超过 10 万次下载。该模型仅用 2048 张 H100 GPU 训练，
    训练成本约 557 万美元，远低于同级别模型。
    """

    print("=" * 60)
    print("测试 1: 用户文本事实提取 (continuation)")
    print("=" * 60)

    result = await extract_facts_from_user_text(test_text, task_type="continuation")
    if result:
        print(result)
        print("\n✅ 事实提取成功")
    else:
        print("\n❌ 事实提取失败（返回 None）")

    print()
    print("=" * 60)
    print("测试 2: 用户文本事实提取 (polish)")
    print("=" * 60)

    result2 = await extract_facts_from_user_text(test_text, task_type="polish")
    if result2:
        print(result2)
        print("\n✅ 事实提取成功")
    else:
        print("\n❌ 事实提取失败（返回 None）")

    print()
    print("=" * 60)
    print("测试 3: 短文本（应跳过）")
    print("=" * 60)

    result3 = await extract_facts_from_user_text("这是一段很短的文字。", task_type="general")
    if result3 is None:
        print("✅ 短文本正确跳过")
    else:
        print("❌ 短文本应该返回 None")


async def test_source_collector_prompt():
    """测试 source_collector 的 prompt 生成（不连数据库）。"""
    from app.services.content_generation.source_collector import (
        SourceMaterial,
        ExtractedFact,
        ArticleFacts,
    )

    print()
    print("=" * 60)
    print("测试 4: SourceMaterial.to_prompt_text()")
    print("=" * 60)

    # 模拟提取结果
    material = SourceMaterial(
        article_count=3,
        total_facts=5,
        facts_by_section={
            1: ["OpenAI 于 2025 年 6 月发布 GPT-5", "参数量 2 万亿"],
            2: ["Claude 4 支持 500K token 上下文", "零越狱成功率"],
            0: ["DeepSeek-V3 训练成本 557 万美元"],
        },
        raw_articles=[
            ArticleFacts(article_id=1, title="GPT-5 发布", url="https://example.com/1", published_at="2025-06-10"),
            ArticleFacts(article_id=2, title="Claude 4 发布", url="https://example.com/2", published_at="2025-06-08"),
        ],
    )

    # 模拟 sections
    class MockSection:
        def __init__(self, num, subtitle):
            self.section_number = num
            self.subtitle = subtitle

    sections = [MockSection(1, "GPT-5 的突破"), MockSection(2, "Claude 4 的优势"), MockSection(3, "国内模型")]

    prompt_text = material.to_prompt_text(sections)
    print(prompt_text)
    print("\n✅ prompt 生成成功")


async def main():
    print("🧪 事实提取模块测试\n")

    await test_user_source_extractor()
    await test_source_collector_prompt()

    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

"""Agent C — 去 AI 味改写员。

职责：按《去 AI 味检查清单》对全文做扫描和改写，把 LLM 默认的"AI 味"文字净化成"人话"。
设计对齐：《正文生成 Agent 设计文档 v1.1》第 4 节 + 《去 AI 味检查清单 v1.0》。
"""

import logging
from typing import List, Optional
from pathlib import Path

from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose
from app.services.content_generation.schemas import (
    AgentAOutput,
    AgentBOutput,
    AgentCOutput,
    AITasteIssue,
)

logger = logging.getLogger(__name__)

# 获取当前文件所在目录
CURRENT_DIR = Path(__file__).parent

# ──────────────────────────────────────────────
# 去 AI 味检查清单（从文件加载）
# ──────────────────────────────────────────────

def _load_deai_checklist() -> str:
    """从文件加载去 AI 味检查清单"""
    checklist_file = CURRENT_DIR / "assets" / "去AI味检查清单.md"
    if checklist_file.exists():
        return checklist_file.read_text(encoding="utf-8")
    # 回退到硬编码版本（如果文件不存在）
    return """\
# 去 AI 味检查清单

## 1. 结构性 AI 味（连接词 / 套话 / 对称）

### 1.1 万恶之首：连接词滥用 🚫
| AI 表达 | 等级 | 改写方向 |
|---------|------|---------|
| 首先、其次、最后 | 🚫 | 直接删，让句子自己接 |
| 一方面、另一方面 | 🚫 | 拆成两段，各说各的 |
| 第一、第二、第三 | ⚠️ | 改成具体内容 |
| 然后、接着、随后 | ⚪ | 多数情况下删掉即可 |
| 此外、另外、除此之外 | ⚪ | 多数可删；要保留时改成"还有件事——" |

### 1.2 总结性套话 🚫
| AI 表达 | 等级 | 改写方向 |
|---------|------|---------|
| 综上所述 | 🚫 | 直接删 |
| 总而言之 | 🚫 | 直接删 |
| 由此可见 | 🚫 | 改成"我的判断是"或直接删 |
| 通过以上分析，我们可以看出 | 🚫 | 直接删整句 |
| 总的来说 | ⚠️ | 改成"说白了"或"一句话" |
| 综合来看 | ⚠️ | 改成"我的感觉是" |

### 1.3 学院式过渡词 ⚠️
| AI 表达 | 等级 | 改写方向 |
|---------|------|---------|
| 值得注意的是 | ⚠️ | 删掉，直接说后面的内容 |
| 值得一提的是 | ⚠️ | 同上 |
| 需要指出的是 | ⚠️ | 同上 |
| 不可忽视的是 | ⚠️ | 同上 |
| 必须强调 | ⚠️ | 同上 |

### 1.4 过度对称结构 ⚠️
症状：连续几段都用同一种开头句式、每个论点都用同样长度的论证、列表项数总是 3/5/7。
改写：强制让段落长度不一致，重点的多写，次要的一笔带过。

## 2. 词汇性 AI 味（学院体 / 程度副词 / 营销话术）

### 2.1 学院化书面体 🚫
| AI 表达 | 等级 | 人话改写 |
|---------|------|---------|
| 在……的情况下 | 🚫 | "A 的时候" |
| 对于……而言 | 🚫 | "X 来说" |
| 在……过程中 | 🚫 | "用着用着" |
| 进行……操作 | 🚫 | "点一下" |
| 实现……功能 | ⚠️ | "能自动跑" |
| 做出……决策 | ⚠️ | "决定买" |
| 针对……方面 | ⚠️ | "效率上" |

### 2.2 客观中立模糊词 ⚠️
| AI 表达 | 等级 | 改写方向 |
|---------|------|---------|
| 在某种程度上 | ⚠️ | 删掉，直接表态 |
| 在一定意义上 | ⚠️ | 同上 |
| 相对而言 | ⚠️ | 改成具体的对比对象 |
| 客观地讲 | ⚠️ | 删掉 |
| 从某种角度来看 | ⚠️ | 改成"如果只看 X" |

### 2.3 程度副词滥用 ⚪
| AI 表达 | 等级 | 改写方向 |
|---------|------|---------|
| 非常、特别、十分、相当 | ⚪ | 整篇 ≤ 2 次 |
| 极其、极度、极为 | ⚠️ | 删掉，用具体细节代替 |
| 显著地、明显地、充分地 | ⚪ | 用数据/具体场景代替 |
| 大幅、大量、大批 | ⚪ | 用具体数字代替 |

### 2.4 营销话术 🚫
| AI 表达 | 等级 | 改写方向 |
|---------|------|---------|
| 革命性、颠覆性、划时代 | 🚫 | 删，改成具体能力描述 |
| 强大的、卓越的、出色的 | 🚫 | 删，改成具体细节 |
| 极致体验 | 🚫 | 删，改成具体场景 |
| 完美解决方案 | 🚫 | 删 |
| 赋能、提质、增效 | 🚫 | 删，企业内部 PPT 用语 |

## 3. 句式性 AI 味（长句 / 对仗 / 被动）

### 3.1 复合长句堆叠 🚫
识别信号：一个句子超过 50 字、含 3 个及以上的"的"、含多个分句。
改写：把长句拆成 2-3 个短句，重要信息独立成句。

### 3.2 强对仗结构 ⚠️
| AI 表达 | 等级 | 改写方向 |
|---------|------|---------|
| 既……又…… | ⚠️ | 拆成两句 |
| 不仅……还…… | ⚠️ | 拆成两句，第二句独立强调 |
| 一是……二是……三是…… | ⚠️ | 改成单独段落 + 各自展开 |

### 3.3 被动句过多 ⚪
| AI 表达 | 等级 | 改写方向 |
|---------|------|---------|
| 被广泛应用于 | ⚪ | "X 在很多地方都在用" |
| 被认为是 | ⚪ | "我觉得 X 是" |
| 被普遍接受 | ⚪ | "大家都认了 X" |

## 4. 情感性 AI 味（最难治的一类）

### 4.1 情感缺失 🚫
识别信号：通篇没有真实情绪词（草、绝了、离谱、爽、痛、慌、震惊）、自嘲、调侃、惊叹。
改写：在关键场景插入 1-2 个真实情绪词，关键发现处用具体反应。

### 4.2 立场缺失 🚫
识别信号："都很优秀，主要看个人需求""各有所长""因人而异""见仁见智"。
改写：必须站队，给出选择建议时要有偏好排序。

### 4.3 故事感缺失 🚫
识别信号：没有具体时间、具体人名/身份、具体场景、具体物。
改写：把"很多人反映"改成具体的人+具体的事，用 5W1H 检查每个故事点。

## 5. 思维性 AI 味（概括 / 平均 / 完美）

### 5.1 概括过度 🚫
识别信号："这给我们带来了启示""由此我们可以总结出""X 时代已经到来"。
改写：保留具体，删掉抽象升华，只在结尾节做 1 次升华。

### 5.2 平均用力 ⚠️
识别信号：5 个论点每个 200 字、列表里每项字数差不多。
改写：主论点写 400 字，辅论点写 100 字，次论点一句话带过。

### 5.3 完美无懈可击 ⚠️
识别信号：通篇没有矛盾、没有疑问、一切都"显而易见"。
改写：关键判断处加入"思维痕迹"，承认不确定，自我打脸。

## 6. 排版性 AI 味（标点 / 列表 / 加粗）

### 6.1 双引号滥用 ⚠️
识别信号：一段里 3 个以上不必要的双引号。
改写：只保留直接引用 + 反讽 + 特殊术语的引号。

### 6.2 列表过度 🚫
识别信号：整篇文章 30% 以上是列表、列表项数 ≥ 5。
改写：整篇列表 ≤ 2 处，单个列表项 ≤ 5 个。

### 6.3 加粗失效 ⚪
识别信号：每段都有加粗。
改写：整篇加粗 ≤ 5 处，加粗放在最反差/最反共识/最金句的地方。

### 6.4 emoji 滥用 ⚠️
识别信号：段落开头加 📌 🎯 💡 🚀 等 emoji。
改写：整篇 emoji ≤ 3 个，只用在标题或关键转折处。

## 7. 一票否决项汇总（🚫）
1. 首先 / 其次 / 最后（作为段落开头）
2. 一方面 / 另一方面
3. 综上所述 / 总而言之 / 由此可见
4. 通过以上分析，我们可以看出
5. 在……的情况下 / 对于……而言 / 在……过程中 / 进行……操作
6. 革命性 / 颠覆性 / 划时代 / 强大的 / 极致 / 完美 / 赋能 / 增效
7. 单句超过 50 字 + 含 3 个"的"以上
8. 通篇无情绪词（草、绝了、离谱、慌、爽、卧槽、好家伙等）
9. "都很优秀，各有所长"类无立场表达
10. 通篇无具体时间 / 地点 / 人物 / 数字
11. 段落开头 emoji（📌 🎯 💡 等）
12. 每段都有加粗（导致加粗失效）
"""


def _load_system_prompt() -> str:
    """从文件加载系统提示词"""
    prompt_file = CURRENT_DIR / "prompts" / "agent_c_system.txt"
    if prompt_file.exists():
        template = prompt_file.read_text(encoding="utf-8")
        return template.format(deai_checklist=_load_deai_checklist())
    # 回退到硬编码版本
    return f"""\
你是去 AI 味改写员。任务是按《去 AI 味检查清单》对正文做净化。

【参考资产】
{_load_deai_checklist()}

【你的工作流（4 步）】

Step 1 - 全文扫描
按 6 大类逐条扫描，识别命中清单的 AI 表达。

Step 2 - 优先级分类
对每处问题按 🚫⚠️⚪🔵 标注。

Step 3 - 改写执行
- 🚫 项：全部改
- ⚠️ 项：每篇出现 > 1 次的要改到 ≤ 1
- ⚪ 项：每篇出现 > 3 次的要改到 ≤ 3
- 🔵 项：酌情改
- 金句标注段落：✋ 跳过，不允许改
- 含具体数据/人名/工具名：✋ 跳过，不允许改

Step 4 - 质量自检
- 字数变化 ≤ ±10%
- 原意保留
- 不引入新 AI 味

【硬约束】
- 改写后字数变化 ≤ ±10%（不允许大砍或大扩）
- 不允许改：标注为"金句"的句子、标注为"直接引用"的句子、含具体数据/工具名/人名的句子
- 必须改：所有 🚫 项
"""


def _build_user_prompt(
    agent_a_output: AgentAOutput,
    agent_b_output: AgentBOutput,
) -> str:
    """构建用户提示词。"""
    lines = []

    # 正文
    lines.append("【正文】")
    lines.append(agent_a_output.full_text)
    lines.append("")

    # 金句清单（不可改）
    lines.append("【金句清单（不可改段落）】")
    for s in agent_b_output.sentences:
        lines.append(f"- 第{s.section_number}节 {s.location}: \"{s.content}\"")
    lines.append("")

    # 输出格式
    lines.append("【输出格式】")
    lines.append("请严格按以下 JSON 格式输出：")
    lines.append("""```json
{
  "rewritten_text": "改写后的完整正文（含小标题标记）",
  "rewrite_table": [
    {
      "location": "第1节第2段",
      "ai_taste_type": "结构性",
      "ai_taste_subtype": "连接词滥用",
      "priority": "🚫",
      "original_text": "原文片段",
      "rewritten_text": "改写后片段",
      "reason": "改写理由"
    }
  ],
  "skipped_sections": [
    "第1节末尾金句：'金句内容'"
  ],
  "stats": {
    "total_issues": 23,
    "rewrite_counts": {"🚫": 8, "⚠️": 4, "⚪": 5, "🔵": 2},
    "skipped": 4
  },
  "quality_check": {
    "original_word_count": 2680,
    "rewritten_word_count": 2620,
    "word_change_pct": -2.2,
    "original_kept": true,
    "new_ai_taste": false
  }
}
```""")

    return "\n".join(lines)


def _parse_llm_output(raw: dict, original_word_count: int) -> AgentCOutput:
    """解析 LLM 输出为 AgentCOutput。"""
    rewrite_table = []
    for item in raw.get("rewrite_table", []):
        rewrite_table.append(AITasteIssue(
            location=item.get("location", ""),
            ai_taste_type=item.get("ai_taste_type", ""),
            ai_taste_subtype=item.get("ai_taste_subtype", ""),
            priority=item.get("priority", "⚪"),
            original_text=item.get("original_text", ""),
            rewritten_text=item.get("rewritten_text", ""),
            reason=item.get("reason", ""),
        ))

    qc = raw.get("quality_check", {})
    rewritten_count = qc.get("rewritten_word_count", len(raw.get("rewritten_text", "")))
    word_change = qc.get("word_change_pct", 0.0)
    if word_change == 0.0 and original_word_count > 0:
        word_change = round((rewritten_count - original_word_count) / original_word_count * 100, 1)

    return AgentCOutput(
        rewritten_text=raw.get("rewritten_text", ""),
        rewritten_word_count=rewritten_count,
        original_word_count=qc.get("original_word_count", original_word_count),
        word_change_pct=word_change,
        rewrite_table=rewrite_table,
        skipped_sections=raw.get("skipped_sections", []),
        stats=raw.get("stats", {}),
        quality_check=qc,
    )


async def deai_rewrite(
    agent_a_output: AgentAOutput,
    agent_b_output: AgentBOutput,
) -> AgentCOutput:
    """Agent C 主入口：去 AI 味改写。

    Args:
        agent_a_output: Agent A 的输出（正文骨干）
        agent_b_output: Agent B 的输出（金句清单，用于识别不可改段落）

    Returns:
        AgentCOutput: 改写后正文 + 改写对照表
    """
    client = get_llm_client()
    user_prompt = _build_user_prompt(agent_a_output, agent_b_output)

    logger.info(f"[Agent C] 开始去 AI 味改写，原文字数: {agent_a_output.total_word_count}")

    messages = [
        ChatMessage(role="system", content=_load_system_prompt()),
        ChatMessage(role="user", content=user_prompt),
    ]

    result = await client.chat(
        messages=messages,
        temperature=0.5,
        max_tokens=8000,
        json_mode=True,
    )

    parsed = parse_json_loose(result.text)
    if not parsed or "rewritten_text" not in parsed:
        logger.error(f"[Agent C] 输出解析失败: {result.text[:300]}")
        raise ValueError("Agent C 输出格式不符合 schema")

    output = _parse_llm_output(parsed, agent_a_output.total_word_count)

    # 自检
    _self_check(output, agent_a_output.total_word_count)

    logger.info(
        f"[Agent C] 去 AI 味完成，改写后字数: {output.rewritten_word_count}，"
        f"变化: {output.word_change_pct}%，改写处数: {len(output.rewrite_table)}"
    )
    return output


def _self_check(output: AgentCOutput, original_word_count: int):
    """Agent C 自检。"""
    warnings = []

    if abs(output.word_change_pct) > 10:
        warnings.append(f"字数变化超限: {output.word_change_pct}%（允许 ±10%）")

    if output.rewritten_word_count < 2000:
        warnings.append(f"改写后字数过少: {output.rewritten_word_count}")

    if warnings:
        logger.warning(f"[Agent C] 自检警告: {'; '.join(warnings)}")

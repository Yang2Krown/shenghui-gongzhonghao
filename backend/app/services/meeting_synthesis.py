"""把会议纪要整理成可复用的方法论，而不是任务 KPI。"""

import json
import logging
from typing import Any, Optional

from app.services.llm import LLMClient, get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose

logger = logging.getLogger(__name__)

MAX_ITEMS = {
    "methodology": 20,
    "checklist": 15,
    "decisions": 20,
    "disagreements": 15,
    "open_questions": 20,
    "follow_ups": 20,
}

# 方法论汇总使用稳定的人工分类，不把分类交给前端临时猜测。
# 会议沉淀 JSON 暂不新增表字段；没有 category 的历史数据也能通过关键词归类。
METHODOLOGY_CATEGORIES = (
    {
        "key": "workflow",
        "title": "写作流程",
        "description": "从想到切入点到真正动笔之前，先把整条写作路线跑通。",
        "keywords": ("先串", "动笔", "对齐", "返工", "写作流程", "骨架"),
    },
    {
        "key": "hook",
        "title": "钩子与标题",
        "description": "判断开头是否成立、是否配得上标题，以及能不能撑起正文。",
        "keywords": ("钩子", "开头", "标题", "切入", "引入", "标题党"),
    },
    {
        "key": "structure",
        "title": "文章结构",
        "description": "明确故事、功能和问题如何串联，让文章结构和重点更清楚。",
        "keywords": ("串联", "串", "结构", "排序", "功能", "大标题", "篇幅"),
    },
    {
        "key": "expression",
        "title": "表达与呈现",
        "description": "把抽象判断换成读者能直接感受到的具体表达和内容安排。",
        "keywords": ("直观", "表达", "形容", "具体", "呈现", "信息"),
    },
    {
        "key": "engagement",
        "title": "互动与评论",
        "description": "在正文和结尾留下真实、具体、值得读者参与的讨论入口。",
        "keywords": ("互动", "评论", "讨论", "读者", "结尾", "评论区"),
    },
    {
        "key": "collaboration",
        "title": "协作与产出",
        "description": "沉淀多人测评、选题分工和内容排期中的协作方式。",
        "keywords": ("双人", "协作", "分工", "排期", "测评", "选题"),
    },
)


def classify_methodology_category(item: dict) -> dict:
    """为方法论或清单项返回稳定分类；显式 category 优先于历史关键词推断。"""
    explicit = str(item.get("category") or "").strip().lower()
    definitions = {category["key"]: category for category in METHODOLOGY_CATEGORIES}
    if explicit in definitions:
        return definitions[explicit]

    text = " ".join(str(item.get(key) or "") for key in (
        "title", "item", "rule", "description", "rationale", "example",
    ))
    if "先串" in text or "动笔前" in text:
        return definitions["workflow"]
    scores = [
        (sum(text.count(keyword) for keyword in category["keywords"]), index, category)
        for index, category in enumerate(METHODOLOGY_CATEGORIES)
    ]
    score, _, category = max(scores, key=lambda value: (value[0], -value[1]))
    return category if score else definitions["workflow"]


class MeetingSynthesisError(ValueError):
    """LLM 输出不能整理成会议沉淀对象时抛出的业务异常。"""


_SYSTEM_PROMPT = """你是内部内容团队的会议方法论整理助手。
你的任务不是把会议变成负责人、采纳率或闭环 KPI，而是把会议中可复用的判断、方法和上下文沉淀下来，供团队以后写文章时直接复用。

严格规则：
1. 完整依据会议原文，不编造会议没有出现的人、结论、数字、截止时间或因果关系。
2. 不要只提取行动项。会议中的方法论、判断规则、争议、理由、已确定事项和未解决问题都要保留。
3. 不要把多个不同原则合并成一句总括。每条明确的方法论单独输出，并尽量保留原文中的例子或依据。
4. 只有会议明确提出的后续事项才放进 follow_ups；没有明确负责人或期限时填 null，不要猜测。
5. `checklist` 要优先提炼“以后每次写文章/做类似工作前需要对齐什么”，而不是泛泛总结。
6. `disagreements` 要区分不同观点和当前倾向；没有分歧时返回空数组。
7. 只输出一个 JSON 对象，不要输出 markdown、解释或额外文字。

输出格式：
{
  "summary": "会议最重要的结论，用 1-3 句话说明",
  "methodology": [
    {
      "title": "方法论名称",
      "rule": "可复用的判断规则",
      "rationale": "为什么这样做",
      "example": "会议中的例子或适用场景",
      "evidence": "支持该规则的原文事实或讨论依据"
    }
  ],
  "checklist": [
    {
      "item": "动笔前要对齐的事项",
      "description": "具体要检查什么",
      "when_to_use": "什么时候使用"
    }
  ],
  "decisions": [
    {"decision": "已经确定的结论", "context": "背景或理由"}
  ],
  "disagreements": [
    {
      "topic": "争议主题",
      "views": ["观点一", "观点二"],
      "current_position": "会议当前更倾向的处理方式"
    }
  ],
  "open_questions": [
    {
      "question": "尚未解决的问题",
      "context": "为什么尚未解决或卡在哪里",
      "next_step": "会议明确提到的下一步；没有则填 null"
    }
  ],
  "follow_ups": [
    {
      "content": "会议明确提出的后续事项",
      "owner": "原文明确提到的负责人或 null",
      "deadline": "原文明确提到的时间或 null"
    }
  ]
}"""


def _text(value: Any, *, max_length: int = 2000) -> Optional[str]:
    if value is None or isinstance(value, (dict, list)):
        return None
    value = str(value).strip()
    return value[:max_length] if value else None


def _parse_json_object(text: str) -> tuple[Optional[dict], str]:
    """解析对象；只有发生闭合/宽松修复时才返回 repaired。"""
    if not text:
        return None, "failed"
    value = text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    def valid(payload: Any) -> Optional[dict]:
        if isinstance(payload, dict):
            for key in ("synthesis", "result", "data"):
                if isinstance(payload.get(key), dict):
                    return payload[key]
            return payload
        return None

    try:
        parsed = valid(json.loads(value))
        if parsed is not None:
            return parsed, "parsed"
    except (TypeError, ValueError, json.JSONDecodeError):
        pass

    parsed = valid(parse_json_loose(value))
    if parsed is not None:
        return parsed, "repaired"

    start = value.find("{")
    if start < 0:
        return None, "failed"
    fragment = value[start:]
    stack: list[str] = []
    in_string = False
    escaped = False
    for char in fragment:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            stack.append("}")
        elif char == "[":
            stack.append("]")
        elif char in {"}", "]"} and stack and stack[-1] == char:
            stack.pop()
    suffix = ('"' if in_string else "") + "".join(reversed(stack))
    try:
        parsed = valid(json.loads(fragment + suffix))
        if parsed is not None:
            logger.info("会议方法论 JSON 自动闭合成功")
            return parsed, "repaired"
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return None, "failed"


def _entry(raw: Any, section: str) -> Optional[dict]:
    if isinstance(raw, str):
        raw = {"content": raw}
    if not isinstance(raw, dict):
        return None

    if section == "methodology":
        rule = _text(raw.get("rule") or raw.get("content") or raw.get("principle"))
        title = _text(raw.get("title") or raw.get("name") or rule, max_length=160)
        if not rule:
            return None
        return {
            "title": title or "未命名方法",
            "rule": rule,
            "rationale": _text(raw.get("rationale") or raw.get("reason")),
            "example": _text(raw.get("example") or raw.get("application")),
            "evidence": _text(raw.get("evidence") or raw.get("source_quote")),
        }
    if section == "checklist":
        item = _text(raw.get("item") or raw.get("content") or raw.get("title"))
        if not item:
            return None
        return {
            "item": item,
            "description": _text(raw.get("description") or raw.get("detail")),
            "when_to_use": _text(raw.get("when_to_use") or raw.get("timing")),
        }
    if section == "decisions":
        decision = _text(raw.get("decision") or raw.get("content") or raw.get("title"))
        if not decision:
            return None
        return {
            "decision": decision,
            "context": _text(raw.get("context") or raw.get("rationale") or raw.get("reason")),
        }
    if section == "disagreements":
        topic = _text(raw.get("topic") or raw.get("content") or raw.get("title"))
        if not topic:
            return None
        views = raw.get("views") or raw.get("positions") or raw.get("viewpoints")
        if isinstance(views, str):
            views = [views]
        if not isinstance(views, list):
            views = []
        return {
            "topic": topic,
            "views": [_text(item) for item in views if _text(item)],
            "current_position": _text(
                raw.get("current_position") or raw.get("conclusion") or raw.get("resolution")
            ),
        }
    if section == "open_questions":
        question = _text(raw.get("question") or raw.get("content") or raw.get("title"))
        if not question:
            return None
        return {
            "question": question,
            "context": _text(raw.get("context") or raw.get("blocker") or raw.get("reason")),
            "next_step": _text(raw.get("next_step") or raw.get("action")),
        }
    if section == "follow_ups":
        content = _text(raw.get("content") or raw.get("action") or raw.get("title"))
        if not content:
            return None
        return {
            "content": content,
            "owner": _text(raw.get("owner") or raw.get("proposer"), max_length=100),
            "deadline": _text(raw.get("deadline") or raw.get("due"), max_length=100),
        }
    return None


def normalize_synthesis_payload(
    payload: dict,
    *,
    raw_output: str = "",
    parse_status: str = "parsed",
) -> dict:
    """把 provider 的对象规范化为稳定的会议沉淀结构。"""
    aliases = {
        "methodology": ("methodology", "principles", "conclusions"),
        "checklist": ("checklist", "alignment_checklist"),
        "decisions": ("decisions", "confirmed_decisions"),
        "disagreements": ("disagreements", "debates", "conflicts"),
        "open_questions": ("open_questions", "unresolved", "questions"),
        "follow_ups": ("follow_ups", "followups", "next_steps"),
    }
    normalized = {
        "summary": _text(
            payload.get("summary")
            or payload.get("executive_summary")
            or payload.get("overview"),
            max_length=4000,
        ),
        "parse_status": parse_status if parse_status in {"parsed", "repaired"} else "parsed",
        "raw_json": {
            "raw_output": raw_output,
            "payload": payload,
            "parse_status": parse_status,
        },
    }
    for section, keys in aliases.items():
        value = next((payload.get(key) for key in keys if payload.get(key) is not None), [])
        if isinstance(value, dict):
            value = [value]
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            value = []
        normalized[section] = [
            item
            for item in (_entry(raw, section) for raw in value)
            if item is not None
        ][:MAX_ITEMS[section]]
    if not normalized["summary"] and not any(normalized[key] for key in MAX_ITEMS):
        raise MeetingSynthesisError("LLM 输出没有可沉淀的会议内容")
    return normalized


async def extract_meeting_synthesis(
    raw_text: str,
    title: str = "",
    *,
    llm_client: Optional[LLMClient] = None,
) -> dict:
    """调用统一 LLM Client，提取会议方法论沉淀对象。"""
    text = raw_text.strip()
    if not text:
        raise MeetingSynthesisError("会议纪要不能为空")

    client = llm_client or get_llm_client()
    result = await client.chat(
        [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=f"会议主题：{title.strip()}\n\n会议纪要全文：\n{text}",
            ),
        ],
        temperature=0.2,
        max_tokens=6000,
        json_mode=True,
    )
    raw_output = result.text or ""
    parse_status = "repaired" if result.finish_reason in {"length", "max_tokens"} else "parsed"
    payload = result.parsed if isinstance(result.parsed, dict) else None
    if payload is not None:
        try:
            synthesis = normalize_synthesis_payload(
                payload,
                raw_output=raw_output or json.dumps(payload, ensure_ascii=False),
                parse_status=parse_status,
            )
        except MeetingSynthesisError:
            # 某些 provider 会先把不完整输出放进 parsed；仍以原始文本再尝试
            # 一次，避免 provider 的宽松解析把“空对象”误判成成功。
            payload, parse_status = _parse_json_object(raw_output)
            if payload is None:
                raise
            synthesis = normalize_synthesis_payload(
                payload,
                raw_output=raw_output,
                parse_status=parse_status,
            )
    else:
        payload, parse_status = _parse_json_object(raw_output)
        if payload is None:
            raise MeetingSynthesisError("LLM 输出无法解析为会议方法论对象")
        synthesis = normalize_synthesis_payload(
            payload,
            raw_output=raw_output,
            parse_status=parse_status,
        )
    synthesis["raw_json"]["finish_reason"] = result.finish_reason
    synthesis["raw_json"]["model"] = result.model
    synthesis["raw_json"]["usage"] = result.usage
    logger.info(
        "会议方法论沉淀完成：输入 %s 字，方法论 %s 条，对齐清单 %s 条，未决问题 %s 条",
        len(text),
        len(synthesis["methodology"]),
        len(synthesis["checklist"]),
        len(synthesis["open_questions"]),
    )
    return synthesis

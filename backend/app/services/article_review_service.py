"""文章复盘的文本分块、重点改动识别和 AI 分析。"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import re
from typing import Any, Optional

from app.services.llm.llm_client import (
    ChatMessage,
    LLMClient,
    get_llm_client,
    parse_json_loose,
)
from app.utils.file_extractor import normalize_extracted_text

logger = logging.getLogger(__name__)

MAX_GROUP_TEXT = 8_000
MAX_ANALYSIS_GROUPS = 40
ANALYSIS_INITIAL_MAX_TOKENS = 32_000
ANALYSIS_RETRY_MAX_TOKENS = 64_000
ANALYSIS_TRUNCATION_REASONS = {"length", "max_tokens"}
SEMANTIC_MAX_BLOCK_CHARS = 720
SEMANTIC_MERGE_TARGET_CHARS = 220
SEMANTIC_SPLIT_TARGET_CHARS = 360
SEMANTIC_TRANSITION_MIN_CHARS = 140


def _clip(value: Any, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}\n……（内容过长，已截断）"


def normalize_review_text(text: str) -> str:
    """统一提取文本中的换行、控制字符和兼容字形。"""

    return normalize_extracted_text(text)


def _is_extraction_noise_line(text: str) -> bool:
    """识别 Word/PDF 提取时常见的独立版本号、页码行、图片占位行。"""

    value = re.sub(r"\s+", "", text or "")
    if not value:
        return False
    # 文章正文里出现的 2.0 等数字通常会嵌在句子中；这里只过滤整行的版本号。
    if re.fullmatch(r"(?:v|ver|version)?\d+(?:\.\d+){1,3}", value, re.IGNORECASE):
        return True
    if re.fullmatch(r"(?:第)?\d+(?:/|／)\d+(?:页)?", value, re.IGNORECASE):
        return True
    if re.fullmatch(r"(?:page|页)\d+(?:/\d+)?", value, re.IGNORECASE):
        return True
    # 图片本身不提取；但图片占位/图注行会在段落间制造“伪边界”，导致语义块被拆开。
    if re.fullmatch(
        r"(?:"
        r"\[?图片\]?|【图片】|\(图片\)|（图片）|"
        r"(?:image|figure|fig\.?\s*\d*)|"
        r"图\d{1,2}(?:[-–—]\d{1,2})?|"
        r"图[:：].{0,20}|"
        r"插图|配图|示意图|截图|流程图|架构图"
        r")",
        value,
        re.IGNORECASE,
    ):
        return True
    return False


def _mask_extraction_noise_lines(source: str) -> str:
    """屏蔽独立提取噪声并保留字符长度/换行，确保偏移和原文行号仍可回溯。"""

    masked: list[str] = []
    for line in source.splitlines(keepends=True):
        content = line.rstrip("\n")
        if _is_extraction_noise_line(content):
            masked.append(re.sub(r"[^\n]", " ", line))
        else:
            masked.append(line)
    return "".join(masked)



# 公众号初稿常见稿头字段；这些行本身没有复盘价值，应在语义分段前跳过。
_FRONT_MATTER_LABEL_RE = re.compile(
    r"^(?:"
    r"发布时间|发布日期|封面|标题|作者|摘要|导语|备注|正文|全文|"
    r"文档类型|稿件类型|稿件状态|状态|栏目|来源|编辑|责编|运营"
    r")\s*[:：]"
)
_FRONT_MATTER_META_RE = re.compile(
    r"^(?:"
    r"作者\s*[|｜].+|"
    r"(?:中科闻歌|磐石ScienceOne|ScienceOne).{0,60}(?:初稿|终稿|定稿|推文)|"
    r".{0,60}(?:公众号推文|公众号文章).{0,30}(?:初稿|终稿|定稿)|"
    r".{0,60}(?:公众号).{0,30}(?:初稿|终稿|定稿)|"
    r"原文第\s*\d+\s*[-–—~至到]\s*\d+\s*行"
    r")$"
)
_BODY_MARKER_RE = re.compile(r"^(?:正文|全文)\s*[:：]\s*(.*)$")


def _is_front_matter_line(text: str) -> bool:
    """识别初稿文件开头常见的元信息行。"""

    value = re.sub(r"\s+", " ", (text or "").strip())
    if not value:
        return True
    if _is_extraction_noise_line(value):
        return True
    compact = re.sub(r"\s+", "", value)
    if compact in {"中科闻歌", "磐石ScienceOne", "ScienceOne"}:
        return True
    if _FRONT_MATTER_LABEL_RE.match(value):
        return True
    if _FRONT_MATTER_META_RE.match(value):
        return True
    # “作者|路人甲TM” 这类
    if re.match(r"^作者\s*[|｜]", value):
        return True
    # 纯标题备选列表：编号标题，常出现在稿头
    if re.match(r"^\d{1,2}[.、．)]\s*\S", value) and len(value) <= 80:
        return True
    # UI 复制残留：02 / 原文第 9-9 行
    if re.fullmatch(r"\d{1,3}", compact):
        return True
    if re.match(r"^原文第\s*\d+", value):
        return True
    if value in {"标题：", "标题:", "封面：", "封面:", "正文：", "正文:", "全文：", "全文:"}:
        return True
    return False


def _looks_like_body_start(text: str) -> bool:
    """启发式判断是否已经进入正文。"""

    value = re.sub(r"\s+", " ", (text or "").strip())
    if not value:
        return False
    if _is_front_matter_line(value):
        return False
    if _BODY_MARKER_RE.match(value):
        return False
    # 以完整叙述句开始，更像正文
    if len(value) >= 12 and re.search(r"[。！？!?…]$", value):
        return True
    # 较长叙述段落，且不是“标题：xxx”字段
    if len(value) >= 20 and "：" not in value[:10] and ":" not in value[:10]:
        return True
    return False


def _find_body_start_offset(source: str) -> int:
    """定位正文起点，跳过稿头元信息与标题备选列表。

    只影响语义块生成范围；原文字符串本身不改写，前端“查看原文全文”
    仍可看到完整内容。若无法可靠识别稿头，则返回 0（全文参与分段）。

    优先识别显式“正文：/全文：”标记；没有标记时，才用稿头元信息 + 叙述句启发式。
    """

    if not source:
        return 0
    lines = list(re.finditer(r"[^\n]*(?:\n|$)", source))
    if not lines:
        return 0

    # 1) 优先找显式正文标记（只在前 80 行内搜索，避免误伤正文里的“正文：”引用）
    for index, match in enumerate(lines[:80]):
        raw = match.group(0)
        if not raw and match.start() == len(source):
            continue
        stripped = raw.rstrip("\n").strip()
        marker = _BODY_MARKER_RE.match(stripped)
        if not marker:
            continue
        inline = (marker.group(1) or "").strip()
        if inline and not _is_front_matter_line(inline):
            # “正文：事情是这样的……” 同行正文
            # 计算 inline 在 raw 中的起点（忽略左侧空白）
            left_ws = len(raw) - len(raw.lstrip(" \t"))
            marker_text = stripped
            inline_in_stripped = marker_text.rfind(inline)
            if inline_in_stripped >= 0:
                return match.start() + left_ws + inline_in_stripped
            return match.start() + left_ws
        # 标记单独成行：取后续第一个非空、非元信息行
        for j in range(index + 1, len(lines)):
            nxt_raw = lines[j].group(0)
            nxt = nxt_raw.rstrip("\n").strip()
            if not nxt:
                continue
            if _is_front_matter_line(nxt):
                continue
            return lines[j].start()
        return match.end()

    # 2) 没有显式标记时：要求开头有足够元信息，再落到第一段叙述正文
    meta_hits = 0
    scanned = 0
    first_body_index = None
    for index, match in enumerate(lines[:80]):
        raw = match.group(0)
        if not raw and match.start() == len(source):
            continue
        stripped = raw.rstrip("\n").strip()
        if not stripped:
            scanned += 1
            continue
        if _is_front_matter_line(stripped):
            meta_hits += 1
            scanned += 1
            continue
        if _looks_like_body_start(stripped):
            first_body_index = index
            break
        # 短标题行（无句号）仍可能是稿头标题，继续当元信息
        if len(stripped) <= 40 and not re.search(r"[。！？!?]", stripped):
            meta_hits += 1
            scanned += 1
            continue
        scanned += 1
        if scanned >= 40:
            break

    if first_body_index is not None and meta_hits >= 3:
        return lines[first_body_index].start()
    return 0


def _slice_semantic_source(source: str) -> tuple[str, int]:
    """返回用于语义分段的正文切片，以及它在原文中的起始偏移。"""

    start = _find_body_start_offset(source)
    if start <= 0:
        return source, 0
    # 若截断后正文过短，说明识别不可靠，回退全文
    body = source[start:]
    if len(re.sub(r"\s+", "", body)) < 40:
        return source, 0
    return body, start


def normalize_semantic_text(text: str) -> str:
    """为语义匹配生成规范化投影，不修改界面展示的原文。"""

    value = normalize_review_text(text)
    value = re.sub(r"\s+", "", value)
    # 全角/半角标点、空格和常见虚词不应单独制造重点修改。
    value = re.sub(r"[，。！？；：、“”‘’（）《》【】…,.!?;:\"'()\[\]<>~—_\-]", "", value)
    value = re.sub(r"[的了着过地得而且也都就呢吧啊呀哦嘛喽]", "", value)
    return value.casefold()


def _is_heading(text: str) -> bool:
    value = re.sub(r"\s+", "", text or "")
    if not value or len(value) > 36:
        return False
    if _is_extraction_noise_line(value):
        return False
    return bool(
        value.startswith("#")
        or re.match(r"^(?:[一二三四五六七八九十]+[、.：:]|\d+[.)、](?!\d)|[（(]\d+[）)])", value)
    )


def _display_segment(source: str, start: int, end: int) -> str:
    return re.sub(r"[ \t]+", " ", source[start:end]).strip()


def _line_units(source: str) -> list[dict]:
    """保留原始行和空行边界，后续再按语义合并。"""

    units: list[dict] = []
    paragraph = 0
    line_no = 1
    for match in re.finditer(r"[^\n]*(?:\n|$)", source):
        raw_line = match.group(0)
        if not raw_line and match.start() == len(source):
            continue
        content = raw_line.rstrip("\n")
        if not content.strip():
            paragraph += 1
        else:
            units.append({
                "start": match.start(),
                "end": match.start() + len(content),
                "line_start": line_no,
                "line_end": line_no,
                "raw_count": 1,
                "paragraph": paragraph,
            })
        line_no += 1
    return units


def _is_structure_marker(text: str) -> bool:
    value = re.sub(r"\s+", "", text or "")
    return bool(re.match(
        r"^(?:第.{0,8}[章节部分步]|[一二三四五六七八九十百]+[、.：:]|"
        r"\d{1,2}[、.．](?!\d)|"
        r"(?:背景|问题|方法|案例|结论|总结|"
        r"第?[一二三四五六七八九十\d]+步)[：:,，]?)",
        value,
    ))


def _is_topic_transition(text: str) -> bool:
    """识别常见论证转折；只在已有足够上下文时才作为新块起点。"""

    value = re.sub(r"\s+", "", text or "")
    return bool(re.match(
        r"^(?:但是|不过|然而|与此同时|接下来|然后|于是|所以|因此|更重要的是|"
        r"换句话说|回到|最后|总的来说|总结一下|先说结论|再来看)",
        value,
    ))


def _is_continuation_line(text: str, previous_text: str = "") -> bool:
    """判断当前行是否更像上一段的续写，而不是新语义块。

    公众号稿常见：图/截图插在两段之间，后面用“这个/那个/上述…”承接前文。
    图片本身不提取，但会在中间留下空档；若按空档或长度硬切，会把续写拆成独立块。
    """

    value = re.sub(r"\s+", "", text or "")
    if not value:
        return False
    if _is_structure_marker(value) or _is_heading(value):
        return False
    # 明确的指代承接（避免“这是第1句…”这类普通叙述被误判）
    if re.match(
        r"^(?:这个|那个|这些|那些|这份|这项|这套|上述|如上|正如|于是|因此|所以|"
        r"接着|随后|然后|紧接着|为此|对此)",
        value,
    ):
        return True
    # “它给出了…” 这类主语承接，仅在较短起句时生效
    if re.match(r"^(?:它|他|她)(?:还|就|又|也)?(?:给出|提供|列|写|说|指出|总结)", value):
        return True
    # 上一句已完整结束，当前句用“主假设/这个结果/这份方案”继续展开
    prev = re.sub(r"\s+", "", previous_text or "")
    if prev and re.search(r"[。！？!?…]$", prev):
        if re.match(r"^(?:主假设|假设|方案|结果|结论|问题|方法|数据|模型)", value):
            return True
        # 当前句直接复用上一句刚出现的核心名词
        for token in ("主假设", "假设", "方案", "结果", "结论", "问题"):
            if token in prev[-40:] and value.startswith(token):
                return True
    return False


def _has_line_level_signal(source: str) -> bool:
    """兼容旧调用方，但不再根据单行长度推断语义边界。"""

    return False


def _split_long_unit(source: str, unit: dict) -> list[dict]:
    raw = source[unit["start"]:unit["end"]]
    if len(raw.strip()) <= SEMANTIC_MAX_BLOCK_CHARS:
        return [unit]

    sentence_matches = list(re.finditer(r".+?(?:[。！？!?；;](?:[”’」』】）)]*)|$)", raw, re.S))
    if not sentence_matches:
        sentence_matches = [re.match(r"[\s\S]+", raw)]
    # 重复排比/模板句常见于公众号正文。把同一句重复几十次拆开会制造
    # 一串“新增”，掩盖真正的整段重写，因此保留为一个语义块。
    sentence_values = {
        normalize_semantic_text(sentence.group(0))
        for sentence in sentence_matches
        if sentence is not None and sentence.group(0).strip()
    }
    if len(sentence_matches) >= 4 and len(sentence_values) <= 2:
        return [unit]
    fragments: list[dict] = []
    fragment_start: Optional[int] = None
    fragment_end: Optional[int] = None
    fragment_len = 0

    def flush() -> None:
        nonlocal fragment_start, fragment_end, fragment_len
        if fragment_start is None or fragment_end is None:
            return
        text = _display_segment(source, unit["start"] + fragment_start, unit["start"] + fragment_end)
        if text:
            absolute_start = unit["start"] + fragment_start
            absolute_end = unit["start"] + fragment_end
            fragments.append({
                "start": absolute_start,
                "end": absolute_end,
                "line_start": source.count("\n", 0, absolute_start) + 1,
                "line_end": source.count("\n", 0, max(absolute_start, absolute_end - 1)) + 1,
                "raw_count": 1,
                "paragraph": unit.get("paragraph"),
            })
        fragment_start = None
        fragment_end = None
        fragment_len = 0

    for sentence in sentence_matches:
        if sentence is None:
            continue
        start, end = sentence.span()
        sentence_len = len(sentence.group(0).strip())
        if fragment_start is None:
            fragment_start = start
        if fragment_len and fragment_len + sentence_len > SEMANTIC_MAX_BLOCK_CHARS:
            flush()
            fragment_start = start
        fragment_end = end
        fragment_len += sentence_len
        if fragment_len >= SEMANTIC_SPLIT_TARGET_CHARS:
            flush()
    flush()
    return fragments or [unit]


def _merge_line_units(units: list[dict]) -> dict:
    """把连续视觉行合成一个待语义切分的候选单元。"""

    return {
        "start": units[0]["start"],
        "end": units[-1]["end"],
        "line_start": units[0]["line_start"],
        "line_end": units[-1]["line_end"],
        "raw_count": sum(item.get("raw_count", 1) for item in units),
        "paragraph": units[0].get("paragraph"),
    }


def build_semantic_blocks(
    text: str,
    *,
    side: str,
    split_short_lines: bool = False,
) -> list[dict]:
    """按主题/论证上下文生成稳定语义块，并保留原文字符位置。"""

    # 只统一换行，不做首尾 strip；这样 start_offset/end_offset 仍然对应
    # 提取文本中的原始字符位置，前端可以准确回溯到原文上下文。
    full_source = _mask_extraction_noise_lines(normalize_review_text(text))
    if not full_source:
        return []
    # 语义分段只对比正文：跳过“中科闻歌 / 公众号推文-初稿 / 标题备选 / 正文：”等稿头。
    # 偏移仍映射回 full_source，保证 source_line_* 与原文行号一致。
    source, body_offset = _slice_semantic_source(full_source)
    if not source.strip():
        source, body_offset = full_source, 0
    raw_units = _line_units(source)
    semantic_units: list[dict] = []
    if split_short_lines:
        for unit in raw_units:
            semantic_units.extend(_split_long_unit(source, unit))
    else:
        # PDF 常把每个视觉文本框输出成“一句 + 空行”。空行只代表排版，不能直接
        # 成为语义边界；将全文连续视觉行放在同一上下文中，再按结构、论证转折和
        # 句子长度切块。这样 Word/PDF 的不同排版不会制造完全不同的分段数量。
        partitions: list[list[dict]] = []
        current: list[dict] = []
        current_chars = 0
        previous_value = ""
        for unit in raw_units:
            value = _display_segment(source, unit["start"], unit["end"])
            normalized_length = len(normalize_semantic_text(value))
            continues_previous = bool(current) and _is_continuation_line(value, previous_value)
            is_boundary = (
                not continues_previous
                and (
                    _is_structure_marker(value)
                    or _is_heading(value)
                    or (
                        current_chars >= SEMANTIC_TRANSITION_MIN_CHARS
                        and _is_topic_transition(value)
                    )
                )
            )
            if is_boundary and current:
                partitions.append(current)
                current = []
                current_chars = 0
            # 长度阈值只在“非续写”处生效，避免图片后的承接句被硬切成新块。
            if (
                current
                and not continues_previous
                and current_chars >= SEMANTIC_MAX_BLOCK_CHARS
                and not _is_structure_marker(value)
            ):
                partitions.append(current)
                current = []
                current_chars = 0
            current.append(unit)
            current_chars += normalized_length
            previous_value = value
        if current:
            partitions.append(current)
        for partition in partitions:
            semantic_units.extend(_split_long_unit(source, _merge_line_units(partition)))

    # 只有明显的语义/结构边界才拆开，避免把每个公众号短句换行误判成独立段落。
    merged: list[dict] = []
    for unit in semantic_units:
        text_value = _display_segment(source, unit["start"], unit["end"])
        if not text_value:
            continue
        current = {**unit, "text": text_value}
        if merged:
            previous = merged[-1]
            previous_match = normalize_semantic_text(previous["text"])
            current_match = normalize_semantic_text(current["text"])
            continues_previous = _is_continuation_line(current["text"], previous["text"])
            can_merge = (
                not split_short_lines
                and not _is_heading(previous["text"])
                and not _is_heading(current["text"])
                and not _is_structure_marker(current["text"])
                and previous["end"] <= current["start"]
                and (
                    continues_previous
                    or len(previous_match) < SEMANTIC_MERGE_TARGET_CHARS
                )
                and (
                    # 续写允许略超目标长度，但仍设硬上限，避免无限吞并
                    len(previous_match) + len(current_match)
                    <= (SEMANTIC_MAX_BLOCK_CHARS + 180 if continues_previous else SEMANTIC_MAX_BLOCK_CHARS)
                )
            )
            if can_merge:
                previous["end"] = current["end"]
                previous["line_end"] = current["line_end"]
                previous["raw_count"] += current["raw_count"]
                previous["text"] = _display_segment(source, previous["start"], previous["end"])
                continue
        merged.append(current)

    blocks: list[dict] = []
    occurrences: dict[str, int] = {}
    for ordinal, unit in enumerate(merged, start=1):
        normalized = normalize_semantic_text(unit["text"])
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
        occurrences[digest] = occurrences.get(digest, 0) + 1
        stable_id = f"sb-{side[:1]}-{digest}-{occurrences[digest]:02d}"
        absolute_start = unit["start"] + body_offset
        absolute_end = unit["end"] + body_offset
        # 行号基于完整原文（含稿头），方便用户对照“查看原文全文”。
        line_start = full_source.count('\n', 0, absolute_start) + 1
        line_end = full_source.count('\n', 0, max(absolute_start, absolute_end - 1)) + 1
        blocks.append({
            "id": stable_id,
            "stable_id": stable_id,
            "side": side,
            "ordinal": ordinal,
            "text": unit["text"],
            "normalized_text": normalized,
            "start_offset": absolute_start,
            "end_offset": absolute_end,
            "source_line_start": line_start,
            "source_line_end": line_end,
            "raw_block_count": unit["raw_count"],
            "user_edited": False,
            "locked": False,
        })
    return blocks


def split_review_blocks(text: str) -> list[str]:
    """兼容旧调用方，但实际使用语义块而非原始换行。"""

    return [block["text"] for block in build_semantic_blocks(text, side="before")]


def _block_similarity(left: dict, right: dict) -> float:
    left_text = left.get("normalized_text") or normalize_semantic_text(left.get("text", ""))
    right_text = right.get("normalized_text") or normalize_semantic_text(right.get("text", ""))
    if not left_text or not right_text:
        return 0.0
    sequence_ratio = difflib.SequenceMatcher(None, left_text, right_text, autojunk=False).ratio()
    left_tokens = set(re.findall(r"[\u4e00-\u9fff]|[a-z0-9]+", left_text))
    right_tokens = set(re.findall(r"[\u4e00-\u9fff]|[a-z0-9]+", right_text))
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    return round(0.72 * sequence_ratio + 0.28 * overlap, 4)


def _classify_pair(
    before: Optional[dict],
    after: Optional[dict],
    similarity: float,
    *,
    order_changed: bool = False,
) -> tuple[str, str, bool, float, str]:
    before_text = before.get("text", "") if before else ""
    after_text = after.get("text", "") if after else ""
    before_normalized = before.get("normalized_text", "") if before else ""
    after_normalized = after.get("normalized_text", "") if after else ""
    change_ratio = round(1 - similarity, 4) if before and after else 1.0
    position_delta = abs((after.get("ordinal", 0) if after else 0) - (before.get("ordinal", 0) if before else 0))
    max_chars = max(len(before_text), len(after_text))

    if before is None:
        kind = "addition"
        return kind, "high" if max_chars >= 80 else "medium", max_chars >= 80, change_ratio, "改后出现了改前没有的语义内容"
    if after is None:
        kind = "deletion"
        return kind, "high" if max_chars >= 80 else "medium", max_chars >= 80, change_ratio, "改前语义内容在改后被删除"
    if before_normalized == after_normalized:
        if order_changed:
            return "reorder", "medium", True, 0.0, "规范化后的内容基本不变，但语义块位置发生变化"
        if before_text == after_text:
            return "unchanged", "low", False, 0.0, "规范化后内容基本一致"
        return "minor_edit", "low", False, 0.0, "规范化后内容基本一致，仅存在低价值格式或虚词变化"
    if similarity >= 0.88 and order_changed and change_ratio <= 0.2:
        return "reorder", "medium", True, change_ratio, "内容变化很小，主要差异来自语义块顺序变化"
    if similarity >= 0.82 or change_ratio <= 0.2:
        return "minor_edit", "low", False, change_ratio, "变化主要是措辞、虚词、标点或轻微表达调整"
    if min(len(before_text), len(after_text)) >= 120 and similarity < 0.75:
        return "rewrite", "high", True, change_ratio, "前后都是完整长语义块，但核心文本相似度较低，优先视为整段重写"
    if position_delta >= 2 and similarity < 0.72:
        return "structural_change", "high", True, change_ratio, "语义内容与位置同时发生明显变化，可能影响文章结构或论证顺序"
    if similarity < 0.5:
        return "uncertain", "high", True, change_ratio, "算法无法仅凭文本相似度确定是重写还是结构性调整，需要人工确认"
    return "structural_change", "medium", max_chars >= 80, change_ratio, "语义内容发生了超过轻微措辞层面的变化"


def build_change_groups(
    before_text: str,
    after_text: str,
    *,
    semantic_blocks: Optional[dict[str, list[dict]]] = None,
) -> dict:
    """以语义块为基本单位做对齐，保留低价值修改并单独识别顺序变化。"""

    if semantic_blocks is None:
        before_blocks = build_semantic_blocks(
            before_text,
            side="before",
        )
        after_blocks = build_semantic_blocks(
            after_text,
            side="after",
        )
    else:
        before_blocks = list(semantic_blocks.get("before") or [])
        after_blocks = list(semantic_blocks.get("after") or [])
    pairs: list[tuple[Optional[int], Optional[int], float]] = []
    used_before: set[int] = set()
    used_after: set[int] = set()

    candidates = []
    for before_index, before in enumerate(before_blocks):
        for after_index, after in enumerate(after_blocks):
            similarity = _block_similarity(before, after)
            exact = before["normalized_text"] == after["normalized_text"]
            if exact or similarity >= 0.55:
                position_penalty = abs(before_index - after_index) * 0.015
                candidates.append((1 if exact else 0, similarity - position_penalty, similarity, before_index, after_index))
    candidates.sort(reverse=True)
    for _exact, _score, similarity, before_index, after_index in candidates:
        if before_index in used_before or after_index in used_after:
            continue
        used_before.add(before_index)
        used_after.add(after_index)
        pairs.append((before_index, after_index, similarity))

    # 同位置的长文本即使相似度很低，也应形成一个“整段重写”对，而不是拆成多处句子替换。
    for index in range(min(len(before_blocks), len(after_blocks))):
        if index in used_before or index in used_after:
            continue
        if min(len(before_blocks[index]["text"]), len(after_blocks[index]["text"])) >= 120:
            used_before.add(index)
            used_after.add(index)
            pairs.append((index, index, _block_similarity(before_blocks[index], after_blocks[index])))

    for index in range(len(before_blocks)):
        if index not in used_before:
            pairs.append((index, None, 0.0))
    for index in range(len(after_blocks)):
        if index not in used_after:
            pairs.append((None, index, 0.0))
    pairs.sort(key=lambda item: min(
        before_blocks[item[0]]["ordinal"] if item[0] is not None else 10_000,
        after_blocks[item[1]]["ordinal"] if item[1] is not None else 10_000,
    ))
    matched_pairs = [
        (before_index, after_index)
        for before_index, after_index, _similarity in pairs
        if before_index is not None and after_index is not None
    ]
    reordered_pairs: set[tuple[int, int]] = set()
    for left_index, left_pair in enumerate(matched_pairs):
        for right_pair in matched_pairs[left_index + 1:]:
            if (left_pair[0] - right_pair[0]) * (left_pair[1] - right_pair[1]) < 0:
                reordered_pairs.update((left_pair, right_pair))

    alignments: list[dict] = []
    groups: list[dict] = []
    reorder_events: list[dict] = []
    for before_index, after_index, similarity in pairs:
        before = before_blocks[before_index] if before_index is not None else None
        after = after_blocks[after_index] if after_index is not None else None
        change_type, impact, is_major, change_ratio, reason = _classify_pair(
            before,
            after,
            similarity,
            order_changed=(before_index, after_index) in reordered_pairs,
        )
        alignment_id = f"change-{len(alignments) + 1:03d}"
        before_ids = [before["stable_id"]] if before else []
        after_ids = [after["stable_id"]] if after else []
        alignment = {
            "id": alignment_id,
            "stable_id": alignment_id,
            "change_type": change_type,
            "kind": {"addition": "insert", "deletion": "delete"}.get(change_type, "replace"),
            "impact": impact,
            "is_major": is_major,
            "confidence": round(similarity if before and after else 0.92, 3),
            "change_ratio": change_ratio,
            "significance_reason": reason,
            "before_block_ids": before_ids,
            "after_block_ids": after_ids,
            "before_block_start": before["ordinal"] if before else None,
            "before_block_end": before["ordinal"] if before else None,
            "after_block_start": after["ordinal"] if after else None,
            "after_block_end": after["ordinal"] if after else None,
            "before_block_count": 1 if before else 0,
            "after_block_count": 1 if after else 0,
            "before_char_count": len(before["text"]) if before else 0,
            "after_char_count": len(after["text"]) if after else 0,
            "before": _clip(before["text"], MAX_GROUP_TEXT) if before else "",
            "after": _clip(after["text"], MAX_GROUP_TEXT) if after else "",
            "position_delta": (after["ordinal"] - before["ordinal"]) if before and after else None,
        }
        alignments.append(alignment)
        if change_type != "unchanged":
            groups.append(alignment)
        if change_type == "reorder":
            reorder_events.append({
                "id": f"reorder-{len(reorder_events) + 1:03d}",
                "before_block_ids": before_ids,
                "after_block_ids": after_ids,
                "summary": "语义内容基本不变，但在文章中的位置发生变化",
                "confidence": alignment["confidence"],
                "before_position": before["ordinal"] if before else None,
                "after_position": after["ordinal"] if after else None,
            })

    major_ids = [group["id"] for group in groups if group["is_major"]]
    return {
        "before_block_count": len(before_blocks),
        "after_block_count": len(after_blocks),
        "total_groups": len(groups),
        "major_group_count": len(major_ids),
        "major_group_ids": major_ids,
        "groups": groups,
        "alignments": alignments,
        "reorder_events": reorder_events,
        "semantic_blocks": {"before": before_blocks, "after": after_blocks},
        "added_blocks": sum(1 for item in groups if item["change_type"] == "addition"),
        "removed_blocks": sum(1 for item in groups if item["change_type"] == "deletion"),
    }


class ArticleReviewAnalysisError(ValueError):
    """LLM 输出无法整理成文章复盘分析对象。"""

    def __init__(self, message: str, *, raw_output: str = "") -> None:
        super().__init__(message)
        self.raw_output = raw_output


_SYSTEM_PROMPT = """你是内部内容团队的文章复盘助手。
你的任务是比较同一篇文章的改前稿和改后稿，只分析输入里真实出现的变化，帮助团队理解“改了什么、为什么改、改完带来了什么效果”，最后提炼可以复用的方法论。

严格规则：
1. 只根据提供的改动块和人工评论作判断，不编造文章没有出现的事实。
2. 每条 key_changes 必须引用一个真实的 change_group_id；无法判断修改原因时，明确写“需要人工确认”，不要伪造动机。
3. methodology_candidates 必须是可复用的写作判断规则，而不是对本篇文章的复述；证据只能来自对应改动块。
4. 只输出一个 JSON 对象，不要输出 Markdown、解释或代码围栏。

输出格式：
{
  "summary": "本次复盘最重要的变化和结果，用 1-3 句话概括",
  "key_changes": [
    {
      "group_id": "change-001",
      "what_changed": "具体改了什么",
      "likely_reason": "修改原因；无法确认时写需要人工确认",
      "effect": "改后对读者理解、结构或转化可能带来的影响",
      "confidence": 0.0
    }
  ],
  "methodology_candidates": [
    {
      "title": "方法论名称",
      "rule": "以后遇到类似文章时可以复用的判断规则",
      "rationale": "为什么这个规则成立",
      "example": "本次复盘中的具体例子",
      "evidence_group_ids": ["change-001"]
    }
  ],
  "open_questions": ["仍需人工确认的问题"]
}""".strip()


def _text(value: Any, *, max_length: int = 2_000) -> Optional[str]:
    if value is None or isinstance(value, (dict, list)):
        return None
    value = str(value).strip()
    return value[:max_length] if value else None


def normalize_article_review_analysis(
    payload: Any,
    *,
    raw_output: str = "",
    parse_status: str = "parsed",
    allow_empty: bool = False,
) -> dict:
    if not isinstance(payload, dict):
        raise ArticleReviewAnalysisError("LLM 输出不是 JSON 对象", raw_output=raw_output)
    summary = _text(payload.get("summary"), max_length=4_000)
    raw_changes = payload.get("key_changes") or payload.get("changes") or []
    raw_candidates = payload.get("methodology_candidates") or payload.get("methodology") or []
    raw_questions = payload.get("open_questions") or payload.get("questions") or []
    if isinstance(raw_changes, dict):
        raw_changes = [raw_changes]
    if isinstance(raw_candidates, dict):
        raw_candidates = [raw_candidates]
    if isinstance(raw_questions, str):
        raw_questions = [raw_questions]
    if not isinstance(raw_changes, list):
        raise ArticleReviewAnalysisError("LLM 输出的 key_changes 不是数组", raw_output=raw_output)
    if not isinstance(raw_candidates, list):
        raise ArticleReviewAnalysisError(
            "LLM 输出的 methodology_candidates 不是数组",
            raw_output=raw_output,
        )
    if not isinstance(raw_questions, list):
        raw_questions = []

    key_changes = []
    for item in raw_changes[:30]:
        if not isinstance(item, dict):
            continue
        group_id = _text(item.get("group_id") or item.get("id"), max_length=80)
        what_changed = _text(item.get("what_changed") or item.get("change"), max_length=2_000)
        if not group_id or not what_changed:
            continue
        confidence = item.get("confidence", 0.0)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = 0.0
        key_changes.append(
            {
                "group_id": group_id,
                "what_changed": what_changed,
                "likely_reason": _text(
                    item.get("likely_reason") or item.get("reason"),
                    max_length=2_000,
                ),
                "effect": _text(item.get("effect") or item.get("impact"), max_length=2_000),
                "confidence": round(confidence, 3),
            }
        )

    candidates = []
    for item in raw_candidates[:20]:
        if isinstance(item, str):
            item = {"title": item, "rule": item}
        if not isinstance(item, dict):
            continue
        rule = _text(item.get("rule") or item.get("content") or item.get("principle"), max_length=2_000)
        if not rule:
            continue
        evidence_ids = item.get("evidence_group_ids") or item.get("group_ids") or []
        if isinstance(evidence_ids, str):
            evidence_ids = [evidence_ids]
        if not isinstance(evidence_ids, list):
            evidence_ids = []
        candidates.append(
            {
                "title": _text(item.get("title") or item.get("name") or rule, max_length=160) or "未命名方法",
                "rule": rule,
                "rationale": _text(item.get("rationale") or item.get("reason"), max_length=2_000),
                "example": _text(item.get("example") or item.get("application"), max_length=2_000),
                "evidence_group_ids": [
                    value for value in (_text(item_id, max_length=80) for item_id in evidence_ids[:10]) if value
                ],
            }
        )

    questions = [
        value
        for value in (_text(item, max_length=1_000) for item in raw_questions[:20])
        if value
    ]
    if not allow_empty and not summary and not key_changes and not candidates:
        raise ArticleReviewAnalysisError("LLM 输出没有可沉淀的复盘内容", raw_output=raw_output)
    return {
        "status": "succeeded",
        "summary": summary,
        "key_changes": key_changes,
        "methodology_candidates": candidates,
        "open_questions": questions,
        "parse_status": parse_status if parse_status in {"parsed", "repaired", "manual"} else "parsed",
        "raw_output": raw_output,
    }


async def analyze_article_review(
    *,
    title: str,
    change_groups: list[dict],
    comments: Optional[list[dict]] = None,
    llm_client: Optional[LLMClient] = None,
) -> dict:
    """调用统一 LLM Client 分析改动块。"""

    if not change_groups:
        return {
            "status": "succeeded",
            "summary": "改前稿和改后稿没有检测到文本变化。",
            "key_changes": [],
            "methodology_candidates": [],
            "open_questions": [],
            "parse_status": "parsed",
            "raw_output": "",
        }
    selected = sorted(
        change_groups,
        key=lambda group: (not group.get("is_major", False), group.get("id", "")),
    )[:MAX_ANALYSIS_GROUPS]
    context = {
        "title": title,
        "changes": selected,
        "human_comments": comments or [],
    }
    client = llm_client or get_llm_client()
    messages = [
        ChatMessage(role="system", content=_SYSTEM_PROMPT),
        ChatMessage(
            role="user",
            content=json.dumps(context, ensure_ascii=False),
        ),
    ]
    retry_count = 0
    try:
        result = await client.chat(
            messages,
            temperature=0.2,
            max_tokens=ANALYSIS_INITIAL_MAX_TOKENS,
            json_mode=True,
        )
        if result.finish_reason in ANALYSIS_TRUNCATION_REASONS:
            retry_count = 1
            logger.warning(
                "文章复盘 AI 输出达到 token 上限，扩大预算重试 initial=%s retry=%s model=%s",
                ANALYSIS_INITIAL_MAX_TOKENS,
                ANALYSIS_RETRY_MAX_TOKENS,
                result.model or getattr(client, "default_model", None),
            )
            result = await client.chat(
                messages,
                temperature=0.2,
                max_tokens=ANALYSIS_RETRY_MAX_TOKENS,
                json_mode=True,
            )
    except Exception as exc:
        raise ArticleReviewAnalysisError(str(exc)[:1_000]) from exc

    raw_output = result.text or ""
    payload = result.parsed if isinstance(result.parsed, dict) else parse_json_loose(raw_output)
    if not isinstance(payload, dict):
        if result.finish_reason in ANALYSIS_TRUNCATION_REASONS:
            raise ArticleReviewAnalysisError(
                "LLM 输出达到 token 上限，已尝试 32K 和 64K 预算仍未完成 JSON，请压缩文章改动块后重试",
                raw_output=raw_output,
            )
        raise ArticleReviewAnalysisError("LLM 输出无法解析为文章复盘 JSON", raw_output=raw_output)
    parse_status = "repaired" if result.finish_reason in ANALYSIS_TRUNCATION_REASONS else "parsed"
    analysis = normalize_article_review_analysis(
        payload,
        raw_output=raw_output,
        parse_status=parse_status,
    )
    analysis.update(
        {
            "model": result.model,
            "usage": result.usage,
            "finish_reason": result.finish_reason,
            "retry_count": retry_count,
        }
    )
    return analysis


def build_review_experience_content(
    review: Any,
    *,
    group_ids: Optional[list[str]] = None,
    custom_content: Optional[str] = None,
) -> str:
    """把人工确认后的复盘结果整理成经验库中的可追溯正文。"""

    if custom_content and custom_content.strip():
        return custom_content.strip()[:50_000]
    groups = list(review.change_groups or [])
    selected_ids = set(group_ids or [group.get("id") for group in groups])
    selected = [group for group in groups if group.get("id") in selected_ids]
    analysis = review.ai_analysis if isinstance(review.ai_analysis, dict) else {}
    sections = [
        "【文章复盘方法论】",
        f"复盘主题：{review.title}",
        f"改前稿：{review.before_filename}",
        f"改后稿：{review.after_filename}",
        "",
        "【AI 差异总结】",
        analysis.get("summary") or "尚未生成 AI 总结，以下保留人工确认的改动。",
    ]
    key_changes = [
        item for item in (analysis.get("key_changes") or [])
        if not selected_ids or item.get("group_id") in selected_ids
    ]
    if key_changes:
        sections.append("\n【关键修改】")
        for item in key_changes:
            sections.append(
                f"- {item.get('group_id')}: {item.get('what_changed')}; "
                f"原因：{item.get('likely_reason') or '需要人工确认'}; "
                f"效果：{item.get('effect') or '待观察'}"
            )
    candidates = analysis.get("methodology_candidates") or []
    if candidates:
        sections.append("\n【可复用方法论】")
        for item in candidates:
            evidence = ", ".join(item.get("evidence_group_ids") or []) or "未标注"
            sections.extend(
                [
                    f"- {item.get('title') or '未命名方法'}：{item.get('rule') or ''}",
                    f"  为什么：{item.get('rationale') or '未说明'}",
                    f"  例子：{item.get('example') or '未说明'}",
                    f"  证据改动块：{evidence}",
                ]
            )
    if selected:
        sections.append("\n【原文证据】")
        for group in selected:
            sections.extend(
                [
                    f"改动块 {group.get('id')}（{group.get('impact')}）",
                    f"改前：{group.get('before') or '（无）'}",
                    f"改后：{group.get('after') or '（无）'}",
                ]
            )
    comments = list(review.comments or [])
    if comments:
        sections.append("\n【人工评论】")
        for comment in comments:
            group_label = comment.change_group_id or "整体"
            sections.append(f"- {group_label}：{comment.body}")
    return "\n".join(sections).strip()[:50_000]

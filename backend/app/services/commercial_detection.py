"""Commercial soft-ad detection for RawInfo articles.

The detector is intentionally a cheap funnel:
1. high-precision structural rules
2. configurable statistical features
3. one short LLM classification when the first two layers are inconclusive
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.services.llm.llm_client import ChatMessage, get_llm_client

logger = logging.getLogger(__name__)


COMMERCIAL_LEVEL_NONE = "none"
COMMERCIAL_LEVEL_SUSPECTED = "suspected"
COMMERCIAL_LEVEL_LIKELY = "likely"


DETECTION_CONFIG: Dict[str, Any] = {
    "platform_domain_allowlist": {
        "mp.weixin.qq.com",
        "weixin.qq.com",
        "weibo.com",
        "zhihu.com",
        "zhuanlan.zhihu.com",
        "juejin.cn",
        "bilibili.com",
        "www.bilibili.com",
        "github.com",
        "x.com",
        "twitter.com",
        "youtube.com",
        "youtu.be",
        "reddit.com",
        "www.reddit.com",
        "news.ycombinator.com",
        "v2ex.com",
    },
    "thresholds": {
        "stat_likely": 0.68,
        "stat_llm": 0.32,
        "stat_suspected": 0.50,
    },
    "feature_weights": {
        "product_name_density": 0.25,
        "call_to_action_count": 0.20,
        "url_outside_platform": 0.15,
        "first_third_intro_block": 0.15,
        "disclaimer_pattern": 0.10,
        "ending_triple_cta": 0.10,
        "brand_mentions": 0.05,
    },
    "llm": {
        "provider": "deepseek",
        "max_content_chars": 1500,
        "max_tokens": 320,
        "temperature": 0.0,
        "prompt_template": """你是一位内容审核员。判断下面这篇公众号文章是否属于“商业软文（商单）”，即作者因收了第三方报酬而把某产品/服务作为文章核心主题推荐。

判断依据：
1. 文章是否围绕某个具体产品/工具/服务展开
2. 是否给出了明确的行动号召（官网/注册/下载/领码/加入群）
3. 前 1/3 是否有一段该产品的简介块（介绍团队/定位/特点）
4. 正文是否多处“先扬后抑”式夸赞 + 主动提局限性

请只输出 JSON：
{{"commercial": true/false, "product": "产品名或空", "reason": "一句话理由"}}

规则统计信号：
{stat_json}

文章标题：{title}
正文节选（前{max_chars}字）：
{excerpt}
""",
    },
}


CTA_PATTERNS = [
    r"免费领取",
    r"扫码",
    r"点击(?:下方|文末)?链接",
    r"回复[【\[].+?[】\]]",
    r"加入(?:社群|交流群|微信群|QQ群)",
    r"立即(?:注册|体验|下载|领取|试用)",
    r"领取(?:资料|福利|优惠|积分|会员)",
    r"专属(?:链接|福利|邀请码|优惠码)",
]

CODE_PATTERNS = [
    r"(?:邀请码|专属码|优惠码|兑换码|口令).{0,12}(?:领取|积分|Pro|会员|优惠|折扣|注册)",
    r"(?:领取|积分|Pro|会员|优惠|折扣|注册).{0,12}(?:邀请码|专属码|优惠码|兑换码|口令)",
]

INTRO_PATTERNS = [
    r"(?:是|由).{0,28}(?:团队|公司|平台|机构).{0,24}(?:推出|打造|发布|开发)",
    r"(?:定位于|主打|专注于|面向).{0,40}(?:工具|平台|服务|产品|应用|解决方案)",
    r"(?:核心功能|主要特点|产品亮点|适合人群|使用场景)",
]

DISCLAIMER_PATTERNS = [
    r"(?:本文|本篇).{0,12}(?:非|不是).{0,12}(?:广告|恰饭|推广)",
    r"(?:利益相关|商业合作|合作内容|赞助)",
    r"(?:仅供参考|不构成投资建议)",
]

URL_PATTERN = re.compile(r"https?://[^\s)）\]】\"'<>]+", re.I)
EN_PRODUCT_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9]*(?:[ ._-][A-Z]?[A-Za-z0-9]+){0,2}\b")
CN_PRODUCT_PATTERN = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]{2,20}(?:AI|智能体|助手|平台|工具|Pro|插件|浏览器|模型)")


@dataclass
class CommercialDetectionResult:
    level: str = COMMERCIAL_LEVEL_NONE
    product: str = ""
    reason: str = ""
    signals: Dict[str, Any] = field(default_factory=dict)

    def to_meta(self) -> Dict[str, Any]:
        return {
            "product": self.product,
            "reason": self.reason,
            "signals": self.signals,
        }


def _normalize_text(title: str, content: str, summary: str = "") -> str:
    parts = [title or "", summary or "", content or ""]
    return "\n".join(p for p in parts if p).strip()


def _domain_from_url(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().removeprefix("www.")
    except Exception:
        return ""


def _is_allowed_domain(domain: str) -> bool:
    if not domain:
        return True
    allowlist = DETECTION_CONFIG["platform_domain_allowlist"]
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in allowlist)


def _count_patterns(patterns: List[str], text: str) -> int:
    return sum(len(re.findall(pattern, text, flags=re.I | re.S)) for pattern in patterns)


def _extract_external_urls(text: str) -> List[str]:
    urls = URL_PATTERN.findall(text or "")
    return [u for u in urls if not _is_allowed_domain(_domain_from_url(u))]


def _candidate_product_counts(text: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    stopwords = {
        "AI", "API", "ChatGPT", "GPT", "OpenAI", "Claude", "GitHub",
        "Google", "Microsoft", "Apple", "Meta", "Pro",
    }
    for pattern in (EN_PRODUCT_PATTERN, CN_PRODUCT_PATTERN):
        for match in pattern.findall(text or ""):
            name = str(match).strip(" ，。！？；：、,.!?;:")
            if len(name) < 2 or name in stopwords:
                continue
            counts[name] = counts.get(name, 0) + 1
    return counts


def _top_product(text: str) -> tuple[str, int]:
    counts = _candidate_product_counts(text)
    if not counts:
        return "", 0
    product, count = max(counts.items(), key=lambda item: item[1])
    return product, count


def _hard_rule_result(title: str, text: str) -> Optional[CommercialDetectionResult]:
    external_urls = _extract_external_urls(text)
    cta_count = _count_patterns(CTA_PATTERNS, text)
    code_hit = _count_patterns(CODE_PATTERNS, f"{title}\n{text}") > 0
    product, product_count = _top_product(text)

    if code_hit:
        return CommercialDetectionResult(
            level=COMMERCIAL_LEVEL_LIKELY,
            product=product,
            reason="出现邀请码/优惠码等商业转化指纹",
            signals={
                "layer": "hard_rule",
                "code_pattern": True,
                "product_mentions": product_count,
            },
        )

    if cta_count >= 2:
        return CommercialDetectionResult(
            level=COMMERCIAL_LEVEL_LIKELY,
            product=product,
            reason="多处出现领取、扫码、点击链接等行动号召",
            signals={
                "layer": "hard_rule",
                "call_to_action_count": cta_count,
                "external_urls": external_urls[:5],
            },
        )

    if external_urls:
        return CommercialDetectionResult(
            level=COMMERCIAL_LEVEL_SUSPECTED,
            product=product,
            reason="正文包含外部引流链接",
            signals={
                "layer": "hard_rule",
                "external_url_count": len(external_urls),
                "external_urls": external_urls[:5],
            },
        )

    return None


def _compute_stat_features(title: str, text: str) -> Dict[str, Any]:
    text_len = max(len(text), 1)
    first_third = text[: max(300, text_len // 3)]
    ending = text[-700:]
    product, product_count = _top_product(f"{title}\n{text}")
    cta_count = _count_patterns(CTA_PATTERNS, text)
    external_urls = _extract_external_urls(text)
    intro_count = _count_patterns(INTRO_PATTERNS, first_third)
    disclaimer_count = _count_patterns(DISCLAIMER_PATTERNS, text)
    ending_cta_count = _count_patterns(CTA_PATTERNS, ending)

    feature_values = {
        "product_name_density": min(product_count / 5, 1.0),
        "call_to_action_count": min(cta_count / 3, 1.0),
        "url_outside_platform": min(len(external_urls) / 2, 1.0),
        "first_third_intro_block": 1.0 if intro_count > 0 else 0.0,
        "disclaimer_pattern": 1.0 if disclaimer_count > 0 else 0.0,
        "ending_triple_cta": min(ending_cta_count / 3, 1.0),
        "brand_mentions": min(product_count / 8, 1.0),
    }
    weights = DETECTION_CONFIG["feature_weights"]
    score = round(sum(feature_values[k] * weights[k] for k in weights), 4)

    return {
        "score": score,
        "features": feature_values,
        "product": product,
        "product_mentions": product_count,
        "call_to_action_count": cta_count,
        "external_urls": external_urls[:5],
        "intro_pattern_count": intro_count,
        "disclaimer_pattern_count": disclaimer_count,
        "ending_cta_count": ending_cta_count,
    }


def _stat_result(stat: Dict[str, Any]) -> Optional[CommercialDetectionResult]:
    thresholds = DETECTION_CONFIG["thresholds"]
    score = stat["score"]
    if score >= thresholds["stat_likely"]:
        return CommercialDetectionResult(
            level=COMMERCIAL_LEVEL_LIKELY,
            product=stat.get("product") or "",
            reason=f"商业结构特征评分较高（{score:.2f}）",
            signals={"layer": "stat_features", **stat},
        )
    if score >= thresholds["stat_suspected"]:
        return CommercialDetectionResult(
            level=COMMERCIAL_LEVEL_SUSPECTED,
            product=stat.get("product") or "",
            reason=f"商业结构特征评分偏高（{score:.2f}）",
            signals={"layer": "stat_features", **stat},
        )
    return None


def _build_llm_prompt(title: str, content: str, stat: Dict[str, Any]) -> str:
    llm_config = DETECTION_CONFIG["llm"]
    max_chars = int(llm_config["max_content_chars"])
    excerpt = (content or "")[:max_chars]
    return llm_config["prompt_template"].format(
        stat_json=json.dumps(stat, ensure_ascii=False),
        title=title,
        max_chars=max_chars,
        excerpt=excerpt,
    )


async def _llm_result(title: str, text: str, stat: Dict[str, Any]) -> CommercialDetectionResult:
    cfg = DETECTION_CONFIG["llm"]
    try:
        client = get_llm_client(cfg.get("provider") or None)
        result = await client.chat(
            [
                ChatMessage(role="system", content="你是严谨的中文内容商业推广识别审核员。"),
                ChatMessage(role="user", content=_build_llm_prompt(title, text, stat)),
            ],
            temperature=float(cfg["temperature"]),
            max_tokens=int(cfg["max_tokens"]),
            json_mode=True,
        )
        parsed = result.parsed or {}
        commercial = bool(parsed.get("commercial"))
        product = str(parsed.get("product") or stat.get("product") or "")
        reason = str(parsed.get("reason") or "")
        return CommercialDetectionResult(
            level=COMMERCIAL_LEVEL_LIKELY if commercial else COMMERCIAL_LEVEL_NONE,
            product=product,
            reason=reason or ("LLM 判断为商业软文" if commercial else "LLM 判断未发现商单结构"),
            signals={
                "layer": "llm",
                "stat": stat,
                "llm": {
                    "provider": getattr(client, "provider", cfg.get("provider")),
                    "model": result.model,
                    "usage": result.usage,
                    "finish_reason": result.finish_reason,
                },
            },
        )
    except Exception as exc:
        logger.warning("商业检测 LLM 分类失败，降级使用统计结果: %s", exc)
        fallback_level = (
            COMMERCIAL_LEVEL_SUSPECTED
            if stat["score"] >= DETECTION_CONFIG["thresholds"]["stat_llm"]
            else COMMERCIAL_LEVEL_NONE
        )
        return CommercialDetectionResult(
            level=fallback_level,
            product=stat.get("product") or "",
            reason="LLM 分类失败，已按规则统计信号降级判断",
            signals={"layer": "llm_fallback", "stat": stat, "error": str(exc)},
        )


async def detect_commercial_article(
    *,
    title: str,
    content: Optional[str] = None,
    summary: Optional[str] = None,
    force_llm: bool = False,
) -> CommercialDetectionResult:
    """Classify an article as none/suspected/likely commercial content."""
    text = _normalize_text(title=title, content=content or "", summary=summary or "")
    hard = _hard_rule_result(title or "", text)
    if hard and not force_llm:
        return hard

    if len(text) < 80:
        return CommercialDetectionResult(
            level=COMMERCIAL_LEVEL_NONE,
            reason="内容过短，未检测到商单结构",
            signals={"layer": "short_text", "text_length": len(text)},
        )

    stat = _compute_stat_features(title or "", text)
    stat_result = _stat_result(stat)
    if stat_result and not force_llm:
        return stat_result

    if force_llm or stat["score"] >= DETECTION_CONFIG["thresholds"]["stat_llm"]:
        return await _llm_result(title or "", text, stat)

    return CommercialDetectionResult(
        level=COMMERCIAL_LEVEL_NONE,
        product=stat.get("product") or "",
        reason="规则和统计特征均未达到商单阈值",
        signals={"layer": "stat_features", **stat},
    )

"""Commercial soft-ad detection for RawInfo articles.

For fixed WeChat ad-monitoring accounts, callers should pass force_llm=True.
That path uses DeepSeek to make the commercial decision and extract structured
placement details. The cheap rule/stat layers remain as a fallback for older
or high-volume sources.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.services.llm.llm_client import ChatMessage, get_llm_client
from app.services.commercial_classification import normalize_commercial_label

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
        "max_content_chars": 3000,
        # DeepSeek V4 Flash may spend well over 700 tokens on reasoning before
        # emitting the JSON result.  2048 avoids truncating normal commercial
        # analyses; the API still stops early when the answer is complete.
        "max_tokens": 2048,
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
    brand: str = ""
    category: str = ""
    reason: str = ""
    advantages: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    signals: Dict[str, Any] = field(default_factory=dict)

    def to_meta(self) -> Dict[str, Any]:
        return {
            "product": self.product,
            "brand": self.brand,
            "category": self.category,
            "reason": self.reason,
            "advantages": self.advantages,
            "evidence": self.evidence,
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


def _finalize_result(result: CommercialDetectionResult) -> CommercialDetectionResult:
    """Keep product only for positive commercial detections.

    The cheap rules compute a noisy "top product candidate" from regex matches.
    For non-commercial articles this is just a debugging signal, not a result.
    Leaving it in the top-level product field makes logs look like the detector
    confidently identified products even when level=none.
    """
    if result.level == COMMERCIAL_LEVEL_NONE:
        result.product = ""
        result.brand = ""
        result.category = ""
        result.advantages = []
        result.evidence = []
    return result


def _clean_list(value: Any, *, limit: int = 5, item_len: int = 80) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text[:item_len])
        if len(out) >= limit:
            break
    return out


def _level_from_llm(parsed: Dict[str, Any]) -> str:
    level = str(parsed.get("level") or parsed.get("confidence") or "").strip().lower()
    if level in {COMMERCIAL_LEVEL_NONE, COMMERCIAL_LEVEL_SUSPECTED, COMMERCIAL_LEVEL_LIKELY}:
        return level
    commercial = bool(parsed.get("commercial"))
    if not commercial:
        return COMMERCIAL_LEVEL_NONE
    return COMMERCIAL_LEVEL_LIKELY


FOREIGN_PRODUCT_NEWS_TERMS = (
    "anthropic", "claude", "openai", "chatgpt", "gpt-4", "gpt-5", "codex",
    "github copilot", "copilot", "gemini", "perplexity", "grok", "xai", "x.ai",
    "google", "meta", "llama", "mistral", "midjourney", "runway", "pika",
    "elevenlabs", "cursor", "windsurf", "lovable", "replit", "notion", "canva",
    "figma", "adobe", "microsoft", "nvidia", "apple", "amazon", "aws",
    "hugging face", "stability ai", "sora", "dall-e", "dalle",
    "马斯克", "谷歌", "微软", "英伟达", "苹果", "亚马逊",
)
COMMERCIAL_OVERRIDE_TERMS = (
    "赞助", "商业合作", "本文由", "广告", "推广合作",
    "中国区代理", "国内代理", "独家代理", "官方授权", "经销",
    "邀请码", "优惠码", "兑换码", "活动码", "专属链接",
)


def _should_downgrade_foreign_product_news(
    *,
    title: str,
    text: str,
    brand: str,
    product: str,
) -> bool:
    haystack = f"{title}\n{brand}\n{product}\n{text[:1200]}".lower()
    if not any(term in haystack for term in FOREIGN_PRODUCT_NEWS_TERMS):
        return False
    return not any(term.lower() in haystack for term in COMMERCIAL_OVERRIDE_TERMS)


def _build_llm_prompt(title: str, content: str, stat: Dict[str, Any]) -> str:
    llm_config = DETECTION_CONFIG["llm"]
    max_chars = int(llm_config["max_content_chars"])
    excerpt = (content or "")[:max_chars]
    return f"""你是公众号商业投放识别分析师。你的任务不是泛泛判断广告，而是判断这篇文章是否像“品牌方给博主投放的商单/商业合作内容”。

业务背景：
- 这些文章来自固定监控的公众号博主，其中相当一部分本来就是商单。
- 不要只依赖“扫码/优惠码/点击链接”。很多软性商单不会写得很硬。
- 重点看：文章是否围绕一个具体产品/服务展开，是否在解释卖点、使用场景、优势、适合人群，是否像帮产品做认知种草。
- 排除：外国产品/国外 AI 大厂工具的普通资讯、教程、测评、更新报道。例如 Claude、ChatGPT、OpenAI、Codex、GitHub Copilot、Gemini、Perplexity、Anthropic、Grok、Google、Meta、Microsoft、Nvidia 等，除非文中明确出现国内代理/官方授权、赞助、商业合作、优惠码/邀请码/专属转化链接，否则不要判为商单。
- 如果文章只是行业新闻、经验分享、工具教程、产品更新解读，判 none。

请只输出 JSON，字段必须完整：
{{
  "commercial": true/false,
  "level": "none/suspected/likely",
  "brand": "投放品牌/甲方；无法判断必须填空字符串",
  "product": "推广产品/服务的官方简称；无法判断必须填空字符串",
  "category": "编程开发/内容创作/图像生成/视频制作/办公效率/数据分析/AI平台/教育学习/营销推广/硬件产品/其他",
  "advantages": ["文章强调的产品优势或卖点，最多4条"],
  "evidence": ["用于判断为商单的文内证据，最多3条"],
  "reason": "一句话说明为什么是或不是商单"
}}

level 规则：
- likely：明显像品牌投放/软文种草，文章主体服务于某个产品/服务推广。
- suspected：有产品种草或转化倾向，但证据不足。
- none：普通资讯/教程/个人分享/国外 AI 产品报道。

程序统计信号仅作参考，不是结论：
{json.dumps(stat, ensure_ascii=False)}

文章标题：{title}
正文节选（前{max_chars}字）：
{excerpt}
"""


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
        level = _level_from_llm(parsed)
        product = normalize_commercial_label(parsed.get("product"))
        brand = normalize_commercial_label(parsed.get("brand"))
        category = str(parsed.get("category") or "").strip()
        reason = str(parsed.get("reason") or "")
        advantages = _clean_list(parsed.get("advantages"), limit=4)
        evidence = _clean_list(parsed.get("evidence"), limit=3)
        if level != COMMERCIAL_LEVEL_NONE and _should_downgrade_foreign_product_news(
            title=title,
            text=text,
            brand=brand,
            product=product,
        ):
            level = COMMERCIAL_LEVEL_NONE
            reason = "外国产品普通资讯/报道，未发现国内代理、授权、赞助或明确转化信号。"
        return _finalize_result(CommercialDetectionResult(
            level=level,
            product=product,
            brand=brand,
            category=category,
            advantages=advantages,
            evidence=evidence,
            reason=reason or ("DeepSeek 判断为商业投放" if level != COMMERCIAL_LEVEL_NONE else "DeepSeek 判断不是商单"),
            signals={
                "layer": "llm",
                "decision": "deepseek_commercial_analysis",
                "stat": stat,
                "llm": {
                    "provider": getattr(client, "provider", cfg.get("provider")),
                    "model": result.model,
                    "usage": result.usage,
                    "finish_reason": result.finish_reason,
                },
            },
        ))
    except Exception as exc:
        logger.warning("商业检测 LLM 分类失败，降级使用统计结果: %s", exc)
        fallback_level = (
            COMMERCIAL_LEVEL_SUSPECTED
            if stat["score"] >= DETECTION_CONFIG["thresholds"]["stat_llm"]
            else COMMERCIAL_LEVEL_NONE
        )
        return _finalize_result(CommercialDetectionResult(
            level=fallback_level,
            product=(stat.get("product") or "") if fallback_level != COMMERCIAL_LEVEL_NONE else "",
            reason="LLM 分类失败，已按规则统计信号降级判断",
            signals={"layer": "llm_fallback", "stat": stat, "error": str(exc)},
        ))


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
        return _finalize_result(hard)

    if len(text) < 80 and not force_llm:
        return _finalize_result(CommercialDetectionResult(
            level=COMMERCIAL_LEVEL_NONE,
            reason="内容过短，未检测到商单结构",
            signals={"layer": "short_text", "text_length": len(text)},
        ))

    stat = _compute_stat_features(title or "", text)
    stat_result = _stat_result(stat)
    if stat_result and not force_llm:
        return _finalize_result(stat_result)

    if force_llm or stat["score"] >= DETECTION_CONFIG["thresholds"]["stat_llm"]:
        return await _llm_result(title or "", text, stat)

    return _finalize_result(CommercialDetectionResult(
        level=COMMERCIAL_LEVEL_NONE,
        reason="规则和统计特征均未达到商单阈值",
        signals={"layer": "stat_features", **stat},
    ))

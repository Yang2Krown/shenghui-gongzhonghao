"""系统安全健康检查。"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from app.core.config import settings


LOCAL_ORIGIN_MARKERS = ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")
WEAK_HOSTS = {"*", "localhost", "127.0.0.1", "0.0.0.0"}


def _level_rank(level: str) -> int:
    return {"ok": 0, "warn": 1, "critical": 2}.get(level, 0)


def _status(level: str, title: str, message: str, *, value: Any = None, actions: Iterable[str] = ()) -> dict:
    return {
        "level": level,
        "title": title,
        "message": message,
        "value": value,
        "actions": list(actions),
    }


def _has_local_origin(origin: Any) -> bool:
    text = str(origin).lower()
    return any(marker in text for marker in LOCAL_ORIGIN_MARKERS)


def _configured(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _masked_presence(name: str, value: Any) -> dict:
    return {"name": name, "configured": _configured(value)}


def collect_security_health(cost_guard_status: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """返回后台可展示的 P2 安全基线状态。"""
    cors_origins = [str(item) for item in settings.BACKEND_CORS_ORIGINS]
    allowed_hosts = [str(item) for item in settings.ALLOWED_HOSTS]
    cors_has_local = any(_has_local_origin(item) for item in cors_origins)
    hosts_have_weak = any(host.lower() in WEAK_HOSTS for host in allowed_hosts)
    hsts_enabled = settings.security_hsts_enabled

    runtime_items = [
        _status(
            "ok" if settings.SECURITY_HEADERS_ENABLED else "critical",
            "安全响应头",
            "已在 API 响应中写入安全响应头" if settings.SECURITY_HEADERS_ENABLED else "未启用安全响应头",
            value="enabled" if settings.SECURITY_HEADERS_ENABLED else "disabled",
            actions=[] if settings.SECURITY_HEADERS_ENABLED else ["开启 SECURITY_HEADERS_ENABLED"],
        ),
        _status(
            "ok" if not settings.is_production or hsts_enabled else "warn",
            "HSTS",
            "生产环境会返回 Strict-Transport-Security" if hsts_enabled else "生产环境未启用 HSTS",
            value="enabled" if hsts_enabled else "disabled",
            actions=[] if hsts_enabled else ["确认 HTTPS 后开启 SECURITY_HSTS_ENABLED"],
        ),
        _status(
            "ok" if settings.RATE_LIMIT_ENABLED else "critical",
            "全局限流",
            "关键入口已接入 Redis 限流" if settings.RATE_LIMIT_ENABLED else "限流已关闭",
            value="enabled" if settings.RATE_LIMIT_ENABLED else "disabled",
            actions=[] if settings.RATE_LIMIT_ENABLED else ["开启 RATE_LIMIT_ENABLED"],
        ),
        _status(
            "ok" if not settings.is_production or not settings.rate_limit_fail_open else "critical",
            "限流失败策略",
            "生产环境 Redis 异常时失败保护" if not settings.rate_limit_fail_open else "Redis 异常时会放行请求",
            value="fail_open" if settings.rate_limit_fail_open else "fail_closed",
            actions=[] if not settings.rate_limit_fail_open else ["生产环境设置 RATE_LIMIT_FAIL_OPEN=false"],
        ),
        _status(
            "ok" if not settings.api_docs_enabled or not settings.is_production else "warn",
            "接口文档暴露",
            "生产环境默认关闭 OpenAPI 文档" if not settings.api_docs_enabled else "当前环境启用了 OpenAPI 文档",
            value="enabled" if settings.api_docs_enabled else "disabled",
            actions=[] if not settings.is_production or not settings.api_docs_enabled else ["生产环境关闭 API_DOCS_ENABLED"],
        ),
    ]

    perimeter_items = [
        _status(
            "ok" if not settings.is_production or not cors_has_local else "critical",
            "CORS 白名单",
            "生产 CORS 未包含本地地址" if not cors_has_local else "CORS 仍包含 localhost/127.0.0.1/0.0.0.0",
            value=", ".join(cors_origins),
            actions=[] if not settings.is_production or not cors_has_local else ["生产环境只保留正式前端域名"],
        ),
        _status(
            "ok" if not settings.is_production or not hosts_have_weak else "critical",
            "Host 白名单",
            "生产 Host 白名单未包含弱主机" if not hosts_have_weak else "Host 白名单仍包含本地或通配主机",
            value=", ".join(allowed_hosts),
            actions=[] if not settings.is_production or not hosts_have_weak else ["生产环境只保留正式 API 域名"],
        ),
        _status(
            "warn",
            "反向代理安全",
            "需要在 Nginx/网关层确认 HTTPS 强制跳转、请求体限制、上传路径访问控制和边缘限流",
            value="manual",
            actions=["检查 Nginx / CDN / Ingress 配置", "确认上传目录不能执行脚本"],
        ),
    ]

    secret_items = [
        _masked_presence("OPENAI_API_KEY", settings.OPENAI_API_KEY),
        _masked_presence("DEEPSEEK_API_KEY", settings.DEEPSEEK_API_KEY),
        _masked_presence("ANTHROPIC_API_KEY", settings.ANTHROPIC_API_KEY),
        _masked_presence("TONGYI_API_KEY", settings.TONGYI_API_KEY),
        _masked_presence("FEISHU_APP_SECRET", settings.FEISHU_APP_SECRET),
        _masked_presence("ALIYUN_SMS_ACCESS_KEY_SECRET", settings.ALIYUN_SMS_ACCESS_KEY_SECRET),
        _masked_presence("WXPAY_API_V3_KEY", settings.WXPAY_API_V3_KEY),
    ]
    configured_secret_count = sum(1 for item in secret_items if item["configured"])

    cost_guard_level = "warn"
    cost_guard_message = "当前已有入口限流和成本看板；每日预算、供应商失败熔断和并发上限仍需继续补齐"
    cost_guard_value = "partial"
    cost_guard_actions = ["增加每日预算阈值", "增加 LLM/短信/图片服务失败熔断"]
    if cost_guard_status:
        guard_overall = cost_guard_status.get("overall") or {}
        blocked_providers = [item for item in cost_guard_status.get("providers") or [] if item.get("blocked")]
        cost_guard_level = "critical" if guard_overall.get("blocked") or blocked_providers else "ok"
        cost_guard_message = guard_overall.get("message") or "LLM 成本防护正常"
        cost_guard_value = f"24h ¥{guard_overall.get('cost_yuan_24h', 0)} / ¥{guard_overall.get('daily_budget_yuan', 0)}"
        cost_guard_actions = [] if cost_guard_level == "ok" else ["查看 provider 熔断状态", "提高预算或排查失败调用"]

    governance_items = [
        _status(
            "ok" if settings.is_production and len(settings.SECRET_KEY) >= 32 or not settings.is_production else "critical",
            "SECRET_KEY 强度",
            "生产环境要求固定强随机密钥" if settings.is_production else "开发环境使用本地密钥",
            value="strong" if len(settings.SECRET_KEY) >= 32 else "dev",
        ),
        _status(
            "warn",
            "密钥轮换",
            f"已检测到 {configured_secret_count} 类外部服务密钥配置；后台只显示配置状态，不回显密钥",
            value=f"{configured_secret_count}/{len(secret_items)}",
            actions=["确认历史泄露密钥已轮换", "生产使用环境变量或只读 secret 挂载"],
        ),
        _status(
            "warn",
            "依赖安全扫描",
            "需要定期运行 Python / Node 依赖漏洞扫描并处理高危项",
            value="manual",
            actions=["后端运行 pip-audit 或 safety", "前端运行 npm audit"],
        ),
        _status(
            cost_guard_level,
            "成本熔断",
            cost_guard_message,
            value=cost_guard_value,
            actions=cost_guard_actions,
        ),
    ]

    groups = [
        {"key": "runtime", "title": "运行时防护", "items": runtime_items},
        {"key": "perimeter", "title": "边界与部署", "items": perimeter_items},
        {"key": "governance", "title": "治理与持续安全", "items": governance_items},
    ]
    all_items = [item for group in groups for item in group["items"]]
    overall_level = max((item["level"] for item in all_items), key=_level_rank)
    counts = {
        "ok": sum(1 for item in all_items if item["level"] == "ok"),
        "warn": sum(1 for item in all_items if item["level"] == "warn"),
        "critical": sum(1 for item in all_items if item["level"] == "critical"),
    }

    return {
        "overall": {
            "level": overall_level,
            "message": "安全基线正常" if overall_level == "ok" else "安全基线有待处理项",
        },
        "counts": counts,
        "environment": settings.ENVIRONMENT,
        "groups": groups,
        "secret_presence": secret_items,
        "cost_guard": cost_guard_status,
    }

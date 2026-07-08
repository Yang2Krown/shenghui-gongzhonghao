"""系统安全健康检查。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional

from app.core.config import settings


LOCAL_ORIGIN_MARKERS = ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")
WEAK_HOSTS = {"*", "localhost", "127.0.0.1", "0.0.0.0"}
REPO_ROOT = Path(__file__).resolve().parents[4]


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


def _file_contains(path: Path, *patterns: str) -> bool:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return all(pattern in content for pattern in patterns)


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
    ]
    nginx_conf = REPO_ROOT / "frontend" / "nginx.conf"
    nginx_hardened = _file_contains(
        nginx_conf,
        "server_tokens off",
        "client_max_body_size",
        "X-Content-Type-Options",
        "limit_except GET HEAD",
    )
    compose_requires_hosts = _file_contains(
        REPO_ROOT / "docker-compose.prod.yml",
        "BACKEND_CORS_ORIGINS: ${BACKEND_CORS_ORIGINS:-[\"https://gzh.midonghub.com\"]}",
        "ALLOWED_HOSTS: ${ALLOWED_HOSTS:-[\"gzh.midonghub.com\"]}",
        "./backend/secrets:/app/secrets:ro",
    )
    proxy_ok = nginx_hardened and compose_requires_hosts and (hsts_enabled or not settings.is_production)
    perimeter_items.append(
        _status(
            "ok" if proxy_ok else "warn",
            "HTTPS 和反向代理安全",
            "生产反代配置已包含基础安全头、请求体限制、上传路径方法限制和只读 secrets 挂载"
            if nginx_hardened and compose_requires_hosts else "反代或生产 compose 仍有安全配置待确认",
            value="configured" if nginx_hardened and compose_requires_hosts else "partial",
            actions=[] if nginx_hardened and compose_requires_hosts else ["检查 frontend/nginx.conf", "检查 docker-compose.prod.yml"],
        )
    )

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
        high_cost_users = cost_guard_status.get("high_cost_users") or []
        cost_guard_level = "critical" if guard_overall.get("blocked") or blocked_providers else ("warn" if high_cost_users else "ok")
        cost_guard_message = guard_overall.get("message") or "LLM 成本防护正常"
        if high_cost_users:
            cost_guard_message += f"；{len(high_cost_users)} 位用户 24 小时成本超过阈值"
        cost_guard_value = f"24h ¥{guard_overall.get('cost_yuan_24h', 0)} / ¥{guard_overall.get('daily_budget_yuan', 0)}"
        cost_guard_actions = [] if cost_guard_level == "ok" else ["查看 provider 熔断状态", "排查高成本用户和失败调用"]

    gitignore_ok = _file_contains(
        REPO_ROOT / ".gitignore",
        ".env.production",
        "backend/secrets/",
        "*.cookie",
        "*.dump",
    )
    dependency_scan_script = REPO_ROOT / "scripts" / "security_scan.sh"
    dependency_scan_ready = dependency_scan_script.exists() and _file_contains(
        dependency_scan_script,
        "pip-audit",
        "npm audit",
    )

    governance_items = [
        _status(
            "ok" if settings.is_production and len(settings.SECRET_KEY) >= 32 or not settings.is_production else "critical",
            "SECRET_KEY 强度",
            "生产环境要求固定强随机密钥" if settings.is_production else "开发环境使用本地密钥",
            value="strong" if len(settings.SECRET_KEY) >= 32 else "dev",
        ),
        _status(
            "ok" if gitignore_ok and compose_requires_hosts else "warn",
            "密钥轮换",
            f"已检测到 {configured_secret_count} 类外部服务密钥配置；后台只显示配置状态，不回显密钥",
            value=f"{configured_secret_count}/{len(secret_items)}",
            actions=[] if gitignore_ok and compose_requires_hosts else ["确认 .gitignore 覆盖 env/secrets", "生产使用环境变量或只读 secret 挂载"],
        ),
        _status(
            "ok" if dependency_scan_ready else "warn",
            "依赖安全扫描",
            "已提供 scripts/security_scan.sh，可扫描 Python 和 Node 依赖高危漏洞"
            if dependency_scan_ready else "需要补齐 Python / Node 依赖漏洞扫描脚本",
            value="ready" if dependency_scan_ready else "missing",
            actions=[] if dependency_scan_ready else ["添加 pip-audit/safety 与 npm audit 扫描入口"],
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

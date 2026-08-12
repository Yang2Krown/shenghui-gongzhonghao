import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import time
import uvicorn

from app.core.config import settings
import app.core.celery_app  # noqa: F401  # 关键：让 API 进程内 @shared_task 发布时绑定正式 Celery 应用，否则任务进无人消费的 celery 默认队列
from app.core.logging_security import install_sensitive_log_filter
from app.core.product_access import (
    PRODUCT_CREATION_TOOL,
    PRODUCT_LABELS,
    PRODUCT_POTENTIAL_COMMERCIAL,
    PRODUCT_PRACTICAL_CAMP,
    PRODUCT_XHS_TOPIC,
    has_product_access,
    is_admin_user,
)
from app.api.v1 import api_router
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal, engine
from app.db.init_db import init_db
from app.models.user import User
from app.services.api_request_logging import api_request_log_writer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
install_sensitive_log_filter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("正在启动AI公众号内容运营平台...")
    
    # 生产结构变更只由 init 容器负责；本地开发仍保留自动建表和初始数据。
    if settings.is_production:
        logger.info("生产环境跳过 Web 进程数据库初始化（由 init 容器负责）")
    else:
        try:
            await init_db()
            logger.info("数据库初始化完成")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise

    await api_request_log_writer.start()
    try:
        yield
    finally:
        await api_request_log_writer.stop()
        logger.info("正在关闭应用...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.api_docs_enabled else None,
    docs_url="/docs" if settings.api_docs_enabled else None,
    redoc_url="/redoc" if settings.api_docs_enabled else None,
    lifespan=lifespan,
    redirect_slashes=False
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def enforce_article_review_request_size(request: Request, call_next):
    """在 FastAPI 解析 multipart 之前拦截过大的文章复盘请求。

    单文件限制由复盘路由再次校验；这里限制整个 HTTP 请求体，给两份 20MB
    文件预留 multipart 边界和表单字段开销。分块传输没有 Content-Length 时，
    路由会再按两份文件的实际字节数校验。
    """
    review_path = f"{settings.API_V1_STR.rstrip('/')}/reviews"
    if request.method == "POST" and request.url.path == review_path:
        raw_length = request.headers.get("content-length")
        try:
            content_length = int(raw_length) if raw_length else None
        except (TypeError, ValueError):
            content_length = None
        if content_length is not None and content_length > settings.ARTICLE_REVIEW_MAX_REQUEST_SIZE:
            actual_mb = content_length / 1024 / 1024
            limit_mb = settings.ARTICLE_REVIEW_MAX_REQUEST_SIZE / 1024 / 1024
            detail = {
                "code": "review_request_too_large",
                "scope": "request",
                "message": (
                    f"本次请求总大小超限：实际 {actual_mb:.2f}MB，"
                    f"限制 {limit_mb:.0f}MB（含 multipart 开销）"
                ),
                "actual_bytes": content_length,
                "limit_bytes": settings.ARTICLE_REVIEW_MAX_REQUEST_SIZE,
            }
            return JSONResponse(
                status_code=413,
                content={"code": 413, "message": detail["message"], "detail": detail},
            )
    return await call_next(request)

# 添加可信主机中间件
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """添加请求处理时间头"""
    start_time = time.time()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        process_time = time.time() - start_time
        if "response" in locals():
            response.headers["X-Process-Time"] = str(process_time)
            _apply_security_headers(response)
        _record_api_request(request, status_code, process_time * 1000)


@app.middleware("http")
async def enforce_membership_gate(request: Request, call_next):
    """Block normal users from product APIs they have not purchased."""
    required_product = _required_product_for_request(request)
    if not required_product:
        return await call_next(request)

    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return await call_next(request)

    payload = decode_token(auth.split(" ", 1)[1])
    if not payload or payload.get("type") != "access" or not payload.get("sub"):
        return await call_next(request)

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return await call_next(request)

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)

    if not user or not user.is_active:
        return await call_next(request)
    if is_admin_user(user) or has_product_access(user, required_product):
        return await call_next(request)

    label = PRODUCT_LABELS.get(required_product, "对应产品")
    return JSONResponse(
        status_code=403,
        content={
            "code": 403,
            "message": f"请先开通{label}后再使用",
            "detail": f"请先开通{label}后再使用",
            "data": {"reason": "product_required", "product": required_product},
        },
    )


def _required_product_for_request(request: Request) -> Optional[str]:
    path = request.url.path
    api_prefix = settings.API_V1_STR.rstrip("/")
    if not path.startswith(f"{api_prefix}/"):
        return None

    relative = path[len(api_prefix):]
    if relative.startswith("/auth/"):
        return None
    if relative == "/users/profile":
        return None
    if relative.startswith("/announcements/"):
        # 系统公告面向全部已登录用户，不能被产品权益门禁拦截。
        return None
    if relative.startswith("/admin/"):
        return None
    if relative in {"/credits/packages", "/credits/operation-costs", "/credits/estimate"}:
        return None
    if relative == "/credits/membership":
        return None
    if relative.startswith("/credits/products/"):
        return None
    if relative.startswith("/credits/purchase/status/"):
        return None
    if relative.startswith("/credits/purchase/close/"):
        # 关闭本人未支付订单本身已由接口校验登录身份和订单归属，
        # 不能再要求用户拥有创作工具产品，否则实战营/积分订单无法关单。
        return None
    if relative == "/credits/pay/notify":
        return None
    if relative.startswith("/docs") or relative.endswith("/openapi.json"):
        return None
    if relative.startswith("/commercial"):
        return PRODUCT_POTENTIAL_COMMERCIAL
    if relative.startswith("/courses"):
        return PRODUCT_PRACTICAL_CAMP
    if relative.startswith((
        "/xhs-publish",
        "/xhs-debug",
        "/xhs-agent",
        "/wechat-to-xhs",
    )):
        # 创作类接口（公众号转小红书、小红书发布/调试/本地采集节点）仍归创作工具。
        return PRODUCT_CREATION_TOOL
    if relative.startswith("/xhs"):
        # 小红书素材库只读选题接口（/xhs/notes、/xhs/topic-boards、/xhs/topics、/xhs/media 等），
        # 灰测期由管理员单独开通「小红书选题」权益。
        return PRODUCT_XHS_TOPIC
    if relative.startswith((
        "/creations",
        "/ai",
        "/styles",
        "/topic-candidates",
        "/topic-clusters",
        "/topics",
        "/outlines",
        "/content-generation",
        "/title-generation",
        "/title-munger",
        "/standalone-title",
        "/generation-records",
        "/image-proxy",
        "/creation-tools",
        "/content-transform",
        "/content-imitate",
        "/wechat-draft",
        "/content-continuation",
        "/content-polish",
        "/wechat-accounts",
        "/images",
        "/_test_gzh_fetch",
    )):
        return PRODUCT_CREATION_TOOL
    if relative.startswith("/progress"):
        return PRODUCT_CREATION_TOOL
    if relative.startswith("/credits/"):
        return PRODUCT_CREATION_TOOL
    return PRODUCT_CREATION_TOOL


def _apply_security_headers(response) -> None:
    """写入基础安全响应头。"""
    if not settings.SECURITY_HEADERS_ENABLED:
        return
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", settings.SECURITY_REFERRER_POLICY)
    response.headers.setdefault("X-Frame-Options", settings.SECURITY_X_FRAME_OPTIONS)
    response.headers.setdefault("Content-Security-Policy", settings.SECURITY_CONTENT_SECURITY_POLICY)
    if settings.security_hsts_enabled:
        response.headers.setdefault(
            "Strict-Transport-Security",
            f"max-age={settings.SECURITY_HSTS_MAX_AGE_SECONDS}; includeSubDomains",
        )


def _record_api_request(request: Request, status_code: int, duration_ms: float) -> None:
    """将接口监测日志放入内存队列，由后台任务批量写库。"""
    try:
        path = request.url.path
        if (
            path in {"/", "/health"}
            or path.startswith("/docs")
            or path.startswith("/redoc")
            or path.startswith("/uploads")
            or path.endswith("/openapi.json")
        ):
            return

        user_id = None
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            payload = decode_token(auth.split(" ", 1)[1])
            if payload and payload.get("sub"):
                try:
                    user_id = int(payload["sub"])
                except (TypeError, ValueError):
                    user_id = None

        api_request_log_writer.enqueue({
            "method": request.method[:10],
            "path": path[:500],
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "user_id": user_id,
        })
    except Exception as exc:
        logger.warning("记录 API 请求监测失败: %s", exc)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "data": None
        }
    )


@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc):
    """404异常处理"""
    return JSONResponse(
        status_code=404,
        content={
            "code": 404,
            "message": "请求的资源不存在",
            "data": None
        }
    )


@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    """验证异常处理"""
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "请求参数验证失败",
            "data": None,
            "detail": str(exc)
        }
    )


# 挂载静态文件服务（用于头像等上传文件）
import os
upload_dir = os.path.abspath("./uploads")
os.makedirs(upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")

# 包含API路由
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    """根路径"""
    return {
        "code": 200,
        "message": "AI公众号内容运营平台API服务运行中",
        "data": {
            "version": settings.VERSION,
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "code": 200,
        "message": "服务健康",
        "data": {
            "status": "healthy",
            "timestamp": time.time()
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

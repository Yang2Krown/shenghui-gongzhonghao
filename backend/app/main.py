import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import time
import uvicorn

from app.core.config import settings
from app.api.v1 import api_router
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal, engine
from app.db.init_db import init_db
from app.models.api_request_log import ApiRequestLog

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("正在启动AI公众号内容运营平台...")
    
    # 初始化数据库
    try:
        await init_db()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise
    
    yield
    
    # 关闭时执行
    logger.info("正在关闭应用...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
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
        await _record_api_request(request, status_code, process_time * 1000)


async def _record_api_request(request: Request, status_code: int, duration_ms: float) -> None:
    """记录后台接口健康监测日志，失败不影响业务请求。"""
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

        async with AsyncSessionLocal() as db:
            db.add(ApiRequestLog(
                method=request.method[:10],
                path=path[:500],
                status_code=status_code,
                duration_ms=round(duration_ms, 2),
                user_id=user_id,
            ))
            await db.commit()
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

"""
健康检查端点

用于监控系统状态和可用性。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.core.config import settings
from app.core.database import get_db

router = APIRouter()


@router.get("/")
async def health_check():
    """
    系统健康检查
    
    返回系统基本状态信息。
    """
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "service": "标题生成Agent系统",
    }


@router.get("/db")
async def database_health(db: AsyncSession = Depends(get_db)):
    """
    数据库健康检查
    
    测试数据库连接是否正常。
    """
    try:
        # 执行简单查询测试连接
        await db.execute("SELECT 1")
        return {
            "status": "healthy",
            "database": "connected",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
        }


@router.get("/redis")
async def redis_health():
    """
    Redis健康检查
    
    测试Redis连接是否正常。
    """
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        await redis_client.ping()
        await redis_client.aclose()
        return {
            "status": "healthy",
            "redis": "connected",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "redis": "disconnected",
            "error": str(e),
        }

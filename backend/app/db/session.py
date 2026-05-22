from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import AsyncGenerator
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# 创建异步引擎
if settings.POSTGRES_PASSWORD:
    # PostgreSQL
    engine = create_async_engine(
        settings.SQLALCHEMY_DATABASE_URI,
        echo=settings.DEBUG,
        future=True,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=10
    )
else:
    # SQLite
    engine = create_async_engine(
        settings.SQLITE_DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
        connect_args={"check_same_thread": False}
    )

# 创建异步会话工厂
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"数据库会话错误: {e}")
            raise
        finally:
            await session.close()


# 同步 session（Celery 任务用）
from sqlalchemy import create_engine

if settings.POSTGRES_PASSWORD:
    _sync_engine = create_engine(
        settings.SQLALCHEMY_DATABASE_URI.replace("+asyncpg", "+psycopg2").replace("postgresql+asyncpg", "postgresql"),
        pool_pre_ping=True,
        pool_size=5,
    )
else:
    _sync_engine = create_engine(
        settings.SQLITE_DATABASE_URL.replace("+aiosqlite", ""),
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(bind=_sync_engine, class_=Session, expire_on_commit=False)


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()
    logger.info("数据库连接已关闭")
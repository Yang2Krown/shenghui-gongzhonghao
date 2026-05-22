import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine, AsyncSessionLocal
from app.models import (
    user, topic, creation, style,
    source_registry, raw_info, info_cluster, topic_candidate, daily_topic_list,
)

logger = logging.getLogger(__name__)


async def init_db():
    """初始化数据库"""
    async with engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表创建完成")
    
    # 创建初始数据
    await create_initial_data()


async def create_initial_data():
    """创建初始数据"""
    async with AsyncSessionLocal() as db:
        try:
            # 检查是否已有管理员用户
            from app.crud.user import user as user_crud
            admin_user = await user_crud.get_by_email(db, email="admin@example.com")
            
            if not admin_user:
                # 创建管理员用户
                from app.schemas.user import UserCreate
                admin_data = UserCreate(
                    username="admin",
                    email="admin@example.com",
                    password="admin123456",
                    full_name="系统管理员"
                )
                admin_user = await user_crud.create(db, obj_in=admin_data)
                
                # 设置为超级用户
                admin_user.is_superuser = True
                admin_user.role = "admin"
                await db.commit()
                await db.refresh(admin_user)
                
                logger.info("管理员用户创建完成")
            
            # 创建默认风格模板
            from app.crud.style import style as style_crud
            default_style = await style_crud.get_by_name(db, name="默认风格")
            
            if not default_style:
                from app.schemas.style import StyleProfileCreate
                style_data = StyleProfileCreate(
                    name="默认风格",
                    description="系统默认的写作风格",
                    style_features={
                        "tone": "专业、客观",
                        "language": "简洁明了",
                        "structure": "总分总",
                        "keywords": ["AI", "人工智能", "技术"],
                        "sentence_length": "中等",
                        "paragraph_length": "3-5句"
                    }
                )
                await style_crud.create(db, obj_in=style_data, user_id=admin_user.id)
                logger.info("默认风格模板创建完成")
            
            logger.info("初始数据创建完成")
            
        except Exception as e:
            logger.error(f"创建初始数据失败: {e}")
            await db.rollback()
            raise


async def drop_db():
    """删除数据库"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        logger.info("数据库表删除完成")


async def reset_db():
    """重置数据库"""
    await drop_db()
    await init_db()
    logger.info("数据库重置完成")
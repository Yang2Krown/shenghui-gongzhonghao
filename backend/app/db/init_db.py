import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import inspect, text

from app.db.base import Base
from app.db.session import engine, AsyncSessionLocal
from app.models import (
    user, topic, creation, style,
    source_registry, raw_info, info_cluster, topic_candidate,
    payment, monitoring, admin_audit, api_request_log, llm_monitoring,
)

logger = logging.getLogger(__name__)


async def init_db():
    """初始化数据库"""
    async with engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_schema_compatibility(conn)
        logger.info("数据库表创建完成")
    
    # 创建初始数据
    await create_initial_data()


async def _ensure_schema_compatibility(conn):
    """补齐 create_all 不会自动更新的兼容字段。

    本项目开发环境里可能先由 Base.metadata.create_all 建表，之后模型增加字段；
    create_all 不会 alter 已存在表，所以这里只做幂等的小修补，避免后台页面因缺列 500。
    正式结构演进仍以 Alembic migration 为准。
    """

    def has_column(sync_conn, table_name: str, column_name: str) -> bool:
        inspector = inspect(sync_conn)
        if not inspector.has_table(table_name):
            return False
        return any(col["name"] == column_name for col in inspector.get_columns(table_name))

    if not await conn.run_sync(has_column, "monitoring_alerts", "handled_by_user_id"):
        await conn.execute(text("ALTER TABLE monitoring_alerts ADD COLUMN handled_by_user_id INTEGER"))
    if not await conn.run_sync(has_column, "monitoring_alerts", "handled_at"):
        await conn.execute(text("ALTER TABLE monitoring_alerts ADD COLUMN handled_at TIMESTAMP"))
    if not await conn.run_sync(has_column, "monitoring_alerts", "note"):
        await conn.execute(text("ALTER TABLE monitoring_alerts ADD COLUMN note TEXT"))

    await conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_monitoring_alerts_handled_by_user_id "
        "ON monitoring_alerts (handled_by_user_id)"
    ))

    if not await conn.run_sync(has_column, "raw_infos", "content_html"):
        await conn.execute(text("ALTER TABLE raw_infos ADD COLUMN content_html TEXT"))
    if not await conn.run_sync(has_column, "raw_infos", "commercial_brand"):
        await conn.execute(text("ALTER TABLE raw_infos ADD COLUMN commercial_brand VARCHAR(100)"))
    if not await conn.run_sync(has_column, "raw_infos", "commercial_category"):
        await conn.execute(text("ALTER TABLE raw_infos ADD COLUMN commercial_category VARCHAR(50)"))
    if not await conn.run_sync(has_column, "raw_infos", "commercial_level"):
        await conn.execute(text(
            "ALTER TABLE raw_infos ADD COLUMN commercial_level VARCHAR(20) NOT NULL DEFAULT 'none'"
        ))
        await conn.execute(text("ALTER TABLE raw_infos ALTER COLUMN commercial_level DROP DEFAULT"))
    if not await conn.run_sync(has_column, "raw_infos", "commercial_meta"):
        await conn.execute(text("ALTER TABLE raw_infos ADD COLUMN commercial_meta JSONB"))

    await conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_raw_infos_commercial_level ON raw_infos (commercial_level)"
    ))
    await conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_raw_infos_commercial_brand ON raw_infos (commercial_brand)"
    ))
    await conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_raw_infos_commercial_category ON raw_infos (commercial_category)"
    ))

    if not await conn.run_sync(has_column, "tasks", "user_id"):
        await conn.execute(text("ALTER TABLE tasks ADD COLUMN user_id INTEGER"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_user_id ON tasks (user_id)"))


async def create_initial_data():
    """创建初始数据"""
    async with AsyncSessionLocal() as db:
        try:
            from app.crud.user import user as user_crud
            from app.core.config import settings

            super_admin = await user_crud.get_by_phone(db, phone=settings.SUPER_ADMIN_PHONE)
            if super_admin:
                changed = False
                if not super_admin.is_superuser:
                    super_admin.is_superuser = True
                    changed = True
                if super_admin.role != "admin":
                    super_admin.role = "admin"
                    changed = True
                if changed:
                    await db.commit()
                    await db.refresh(super_admin)
                    logger.info("最高管理员手机号已授予权限: %s", settings.SUPER_ADMIN_PHONE)
            
            # 创建默认风格模板
            from app.crud.style import style as style_crud
            default_style = await style_crud.get_by_name(db, name="默认风格")
            
            if not default_style:
                owner_user = super_admin
                if not owner_user:
                    logger.info("最高管理员手机号用户尚未创建，跳过默认风格模板创建")
                    logger.info("初始数据创建完成")
                    return

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
                await style_crud.create(db, obj_in=style_data, user_id=owner_user.id)
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

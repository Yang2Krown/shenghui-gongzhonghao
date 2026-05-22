"""Alembic env：复用 app.core.config 的数据库 URL 和 Base.metadata。

注意：Alembic 用同步驱动跑迁移，所以把 'postgresql+asyncpg://' 切成 'postgresql+psycopg2://'。
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# 把 backend/ 加进 sys.path，以便 import app.*
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# 注意：导入顺序——先 settings，再触发所有模型注册
from app.core.config import settings
from app.db.base import Base
import app.models  # noqa: F401 触发所有 model 注册到 Base.metadata


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _sync_db_url() -> str:
    """同步驱动版本的 URL，给 alembic 用。"""
    url = settings.SQLALCHEMY_DATABASE_URI
    # alembic 同步执行：asyncpg → psycopg2
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    # 同理 aiosqlite → sqlite
    if url.startswith("sqlite+aiosqlite://"):
        url = url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


# 把同步 URL 注入 alembic.ini
config.set_main_option("sqlalchemy.url", _sync_db_url())

target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    """Autogenerate hook：让 pgvector 的 Vector 类型在迁移文件里自动加 import。"""
    if type_ == "type" and obj.__class__.__module__.startswith("pgvector"):
        autogen_context.imports.add("import pgvector.sqlalchemy")
        return f"pgvector.sqlalchemy.Vector(dim={obj.dim})"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_db_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,           # 检测列类型变化
        compare_server_default=True, # 检测 default 变化
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_item=render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

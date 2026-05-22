from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.db.base import BaseModel as DBBaseModel

ModelType = TypeVar("ModelType", bound=DBBaseModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """基础CRUD操作类"""
    
    def __init__(self, model: Type[ModelType]):
        """
        初始化CRUD对象
        :param model: SQLAlchemy模型类
        """
        self.model = model
    
    async def get(self, db: AsyncSession, id: Any) -> Optional[ModelType]:
        """
        根据ID获取记录
        :param db: 数据库会话
        :param id: 记录ID
        :return: 记录对象或None
        """
        statement = select(self.model).where(self.model.id == id)
        result = await db.execute(statement)
        return result.scalars().first()
    
    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Any = None
    ) -> List[ModelType]:
        """
        获取多条记录
        :param db: 数据库会话
        :param skip: 跳过记录数
        :param limit: 限制记录数
        :param filters: 筛选条件
        :return: 记录列表
        """
        statement = select(self.model)
        
        if filters:
            # 应用筛选条件
            if hasattr(filters, 'category') and filters.category:
                statement = statement.where(self.model.category == filters.category)
            if hasattr(filters, 'platform') and filters.platform:
                statement = statement.where(self.model.source_platform == filters.platform)
            if hasattr(filters, 'keyword') and filters.keyword:
                statement = statement.where(
                    or_(
                        self.model.title.contains(filters.keyword),
                        self.model.content_summary.contains(filters.keyword)
                    )
                )
        
        # 排序
        if hasattr(filters, 'sort_by') and filters.sort_by:
            sort_column = getattr(self.model, filters.sort_by, self.model.created_at)
            if hasattr(filters, 'sort_order') and filters.sort_order == "desc":
                statement = statement.order_by(sort_column.desc())
            else:
                statement = statement.order_by(sort_column.asc())
        else:
            statement = statement.order_by(self.model.created_at.desc())
        
        # 分页
        statement = statement.offset(skip).limit(limit)
        
        result = await db.execute(statement)
        return result.scalars().all()
    
    async def count(
        self,
        db: AsyncSession,
        *,
        filters: Any = None
    ) -> int:
        """
        统计记录数
        :param db: 数据库会话
        :param filters: 筛选条件
        :return: 记录总数
        """
        statement = select(func.count()).select_from(self.model)
        
        if filters:
            # 应用筛选条件
            if hasattr(filters, 'category') and filters.category:
                statement = statement.where(self.model.category == filters.category)
            if hasattr(filters, 'platform') and filters.platform:
                statement = statement.where(self.model.source_platform == filters.platform)
            if hasattr(filters, 'keyword') and filters.keyword:
                statement = statement.where(
                    or_(
                        self.model.title.contains(filters.keyword),
                        self.model.content_summary.contains(filters.keyword)
                    )
                )
        
        result = await db.execute(statement)
        return result.scalar()
    
    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateSchemaType,
        **kwargs
    ) -> ModelType:
        """
        创建记录
        :param db: 数据库会话
        :param obj_in: 创建数据
        :param kwargs: 额外参数
        :return: 创建的记录
        """
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data, **kwargs)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """
        更新记录
        :param db: 数据库会话
        :param db_obj: 数据库对象
        :param obj_in: 更新数据
        :return: 更新后的记录
        """
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def remove(
        self,
        db: AsyncSession,
        *,
        id: int
    ) -> Optional[ModelType]:
        """
        删除记录
        :param db: 数据库会话
        :param id: 记录ID
        :return: 删除的记录
        """
        statement = select(self.model).where(self.model.id == id)
        result = await db.execute(statement)
        obj = result.scalars().first()
        
        if obj:
            await db.delete(obj)
            await db.commit()
        
        return obj
    
    async def exists(
        self,
        db: AsyncSession,
        **kwargs
    ) -> bool:
        """
        检查记录是否存在
        :param db: 数据库会话
        :param kwargs: 筛选条件
        :return: 是否存在
        """
        statement = select(func.count()).select_from(self.model)
        
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                statement = statement.where(getattr(self.model, key) == value)
        
        result = await db.execute(statement)
        return result.scalar() > 0
    
    async def get_by_field(
        self,
        db: AsyncSession,
        field: str,
        value: Any
    ) -> Optional[ModelType]:
        """
        根据字段获取记录
        :param db: 数据库会话
        :param field: 字段名
        :param value: 字段值
        :return: 记录对象或None
        """
        if not hasattr(self.model, field):
            return None
        
        statement = select(self.model).where(getattr(self.model, field) == value)
        result = await db.execute(statement)
        return result.scalars().first()
    
    async def get_multi_by_field(
        self,
        db: AsyncSession,
        field: str,
        value: Any,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """
        根据字段获取多条记录
        :param db: 数据库会话
        :param field: 字段名
        :param value: 字段值
        :param skip: 跳过记录数
        :param limit: 限制记录数
        :return: 记录列表
        """
        if not hasattr(self.model, field):
            return []
        
        statement = (
            select(self.model)
            .where(getattr(self.model, field) == value)
            .offset(skip)
            .limit(limit)
        )
        
        result = await db.execute(statement)
        return result.scalars().all()
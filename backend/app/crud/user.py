from typing import Any, Dict, Optional, Union
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.crud.base import CRUDBase
from app.models.user import User, UserProfile
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserProfileCreate,
    UserProfileUpdate
)


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    """用户CRUD操作类"""
    
    async def get_by_email(
        self,
        db: AsyncSession,
        *,
        email: str
    ) -> Optional[User]:
        """
        根据邮箱获取用户
        :param db: 数据库会话
        :param email: 邮箱地址
        :return: 用户对象或None
        """
        statement = select(User).where(User.email == email)
        result = await db.execute(statement)
        return result.scalars().first()
    
    async def get_by_username(
        self,
        db: AsyncSession,
        *,
        username: str
    ) -> Optional[User]:
        """
        根据用户名获取用户
        :param db: 数据库会话
        :param username: 用户名
        :return: 用户对象或None
        """
        statement = select(User).where(User.username == username)
        result = await db.execute(statement)
        return result.scalars().first()
    
    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: UserCreate
    ) -> User:
        """
        创建用户
        :param db: 数据库会话
        :param obj_in: 用户创建数据
        :return: 创建的用户
        """
        # 创建用户对象
        db_obj = User(
            username=obj_in.username,
            email=obj_in.email,
            hashed_password=get_password_hash(obj_in.password),
            full_name=obj_in.full_name,
            avatar_url=obj_in.avatar_url,
            is_active=True,
            is_superuser=False,
            role="user"
        )
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        
        # 创建用户资料
        profile = UserProfile(user_id=db_obj.id)
        db.add(profile)
        await db.commit()
        
        return db_obj
    
    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: User,
        obj_in: Union[UserUpdate, Dict[str, Any]]
    ) -> User:
        """
        更新用户
        :param db: 数据库会话
        :param db_obj: 数据库用户对象
        :param obj_in: 更新数据
        :return: 更新后的用户
        """
        return await super().update(db, db_obj=db_obj, obj_in=obj_in)
    
    async def authenticate(
        self,
        db: AsyncSession,
        *,
        email: str,
        password: str
    ) -> Optional[User]:
        """
        用户认证
        :param db: 数据库会话
        :param email: 邮箱地址
        :param password: 密码
        :return: 认证成功返回用户，否则返回None
        """
        user = await self.get_by_email(db, email=email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
    
    async def is_active(
        self,
        user: User
    ) -> bool:
        """
        检查用户是否激活
        :param user: 用户对象
        :return: 是否激活
        """
        return user.is_active
    
    async def is_superuser(
        self,
        user: User
    ) -> bool:
        """
        检查用户是否是超级用户
        :param user: 用户对象
        :return: 是否是超级用户
        """
        return user.is_superuser
    
    async def get_profile(
        self,
        db: AsyncSession,
        *,
        user_id: int
    ) -> Optional[UserProfile]:
        """
        获取用户资料
        :param db: 数据库会话
        :param user_id: 用户ID
        :return: 用户资料对象或None
        """
        statement = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await db.execute(statement)
        return result.scalars().first()
    
    async def update_profile(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        profile_in: UserProfileUpdate
    ) -> Optional[UserProfile]:
        """
        更新用户资料
        :param db: 数据库会话
        :param user_id: 用户ID
        :param profile_in: 更新数据
        :return: 更新后的用户资料
        """
        profile = await self.get_profile(db, user_id=user_id)
        
        if not profile:
            # 如果不存在则创建
            profile = UserProfile(user_id=user_id)
            db.add(profile)
        
        # 更新资料字段
        update_data = profile_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(profile, field) and field not in ["full_name", "avatar_url"]:
                setattr(profile, field, value)
        
        await db.commit()
        await db.refresh(profile)
        
        return profile
    
    async def update_password(
        self,
        db: AsyncSession,
        *,
        user: User,
        new_password: str
    ) -> User:
        """
        更新用户密码
        :param db: 数据库会话
        :param user: 用户对象
        :param new_password: 新密码
        :return: 更新后的用户
        """
        user.hashed_password = get_password_hash(new_password)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    
    async def update_last_login(
        self,
        db: AsyncSession,
        *,
        user: User
    ) -> User:
        """
        更新最后登录时间
        :param db: 数据库会话
        :param user: 用户对象
        :return: 更新后的用户
        """
        from datetime import datetime
        user.last_login = datetime.utcnow()
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


# 创建用户CRUD实例
user = CRUDUser(User)
"""创作发布状态服务。

这里把状态改变和发布记录放在同一个事务里，保证重复请求只得到同一条业务记录，
并为后续接入真实平台回调保留 pending/failed 状态。
"""

from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import utcnow
from app.models.creation import ContentCreation
from app.models.creation_publication import CreationPublication


def _normalized_request_key(request_key: Optional[str]) -> Optional[str]:
    value = (request_key or "").strip()
    return value or None


def _publication_filters(
    *,
    creation_id: int,
    platform: str,
    operation: str,
    request_key: Optional[str],
) -> list:
    filters = [
        CreationPublication.creation_id == creation_id,
        CreationPublication.platform == platform,
        CreationPublication.operation == operation,
    ]
    normalized_key = _normalized_request_key(request_key)
    if normalized_key is None:
        # 兼容旧客户端：没有幂等键时，同一个创作/平台/动作只维护一条
        # legacy 当前记录，避免升级后重复产生本地状态。
        filters.append(CreationPublication.request_key.is_(None))
    else:
        filters.append(CreationPublication.request_key == normalized_key)
    return filters


async def _get_locked_publication(
    db: AsyncSession,
    *,
    creation_id: int,
    platform: str,
    operation: str,
    request_key: Optional[str],
) -> Optional[CreationPublication]:
    return (await db.execute(
        select(CreationPublication)
        .where(*_publication_filters(
            creation_id=creation_id,
            platform=platform,
            operation=operation,
            request_key=request_key,
        ))
        .with_for_update()
    )).scalars().first()


async def begin_creation_publication(
    db: AsyncSession,
    *,
    creation_id: int,
    initiated_by: int,
    platform: str,
    operation: str,
    request_key: str,
) -> Tuple[ContentCreation, CreationPublication, bool]:
    """在执行外部推送前占用幂等键。

    返回的第三个值表示是否命中已有请求。命中 succeeded 时调用方可直接返回；
    命中 pending 时调用方应拒绝并等待原请求，避免两个请求同时推送。
    """
    normalized_key = _normalized_request_key(request_key)
    if normalized_key is None:
        raise ValueError("外部推送必须提供 request_key")
    creation = (await db.execute(
        select(ContentCreation)
        .where(ContentCreation.id == creation_id)
        .with_for_update()
    )).scalars().first()
    if creation is None:
        raise ValueError("创作不存在")
    publication = await _get_locked_publication(
        db,
        creation_id=creation_id,
        platform=platform,
        operation=operation,
        request_key=normalized_key,
    )
    if publication is not None:
        if publication.status == "succeeded":
            return creation, publication, True
        if publication.status == "pending":
            return creation, publication, True
        # failed 记录允许原 request_key 重试，仍然复用原记录。
        publication.status = "pending"
        publication.error_message = None
        publication.started_at = utcnow()
        publication.finished_at = None
        await db.commit()
        await db.refresh(creation)
        await db.refresh(publication)
        return creation, publication, False

    now = utcnow()
    publication = CreationPublication(
        creation_id=creation_id,
        initiated_by=initiated_by,
        platform=platform,
        operation=operation,
        status="pending",
        request_key=normalized_key,
        started_at=now,
    )
    db.add(publication)
    await db.commit()
    await db.refresh(creation)
    await db.refresh(publication)
    return creation, publication, False


async def record_creation_publication(
    db: AsyncSession,
    *,
    creation_id: int,
    initiated_by: int,
    platform: str,
    operation: str,
    external_id: Optional[str] = None,
    external_url: Optional[str] = None,
    request_key: Optional[str] = None,
) -> Tuple[ContentCreation, CreationPublication, bool]:
    """记录一次成功的草稿上传/正式发布，并返回是否幂等命中。

    生产数据库使用文章行锁串行化同一创作的并发请求；业务唯一键则作为第二层
    防线，避免同一个 request_key 重复创建相同的外部动作记录；没有幂等键的旧
    客户端则沿用同一条 legacy 当前记录。
    """
    creation = (await db.execute(
        select(ContentCreation)
        .where(ContentCreation.id == creation_id)
        .with_for_update()
    )).scalars().first()
    if creation is None:
        raise ValueError("创作不存在")

    publication = await _get_locked_publication(
        db,
        creation_id=creation_id,
        platform=platform,
        operation=operation,
        request_key=request_key,
    )
    if publication is not None and publication.status == "succeeded":
        return creation, publication, True

    now = utcnow()
    if publication is None:
        publication = CreationPublication(
            creation_id=creation_id,
            initiated_by=initiated_by,
            platform=platform,
            operation=operation,
            status="pending",
            request_key=_normalized_request_key(request_key),
            started_at=now,
        )
        db.add(publication)
    else:
        # failed/pending 记录可以被同一个业务动作恢复，不创建第二条记录。
        publication.initiated_by = initiated_by
        publication.status = "pending"
        publication.started_at = publication.started_at or now
        publication.request_key = _normalized_request_key(request_key) or publication.request_key

    publication.external_id = external_id or publication.external_id
    publication.external_url = external_url or publication.external_url
    publication.status = "succeeded"
    publication.error_message = None
    publication.finished_at = now

    if operation == "draft_upload":
        # 正式发布后的文章不能被一次迟到的草稿回写降级。
        if creation.status != "published":
            creation.status = "wechat_draft"
        creation.published_platform = platform
        if external_url:
            creation.platform_url = external_url
    elif operation == "publish":
        creation.status = "published"
        creation.published_at = creation.published_at or now
        creation.published_platform = platform
        if external_url:
            creation.platform_url = external_url

    creation.updated_at = now
    await db.commit()
    await db.refresh(creation)
    await db.refresh(publication)
    return creation, publication, False


async def fail_creation_publication(
    db: AsyncSession,
    *,
    creation_id: int,
    initiated_by: int,
    platform: str,
    operation: str,
    error_message: str,
    request_key: Optional[str] = None,
) -> CreationPublication:
    """记录一次可重试的外部发布失败，不改变本地创作生命周期。"""
    publication = await _get_locked_publication(
        db,
        creation_id=creation_id,
        platform=platform,
        operation=operation,
        request_key=request_key,
    )
    if publication is not None and publication.status == "succeeded":
        # 外部调用和本地回写已经成功时，后续响应序列化/网络异常不能把事实
        # 状态倒退为 failed；客户端可用同一个 request_key 再次读取结果。
        return publication
    now = utcnow()
    if publication is None:
        publication = CreationPublication(
            creation_id=creation_id,
            initiated_by=initiated_by,
            platform=platform,
            operation=operation,
            started_at=now,
            request_key=_normalized_request_key(request_key),
        )
        db.add(publication)
    publication.status = "failed"
    publication.error_message = error_message[:2000]
    publication.finished_at = now
    publication.request_key = _normalized_request_key(request_key) or publication.request_key
    await db.commit()
    await db.refresh(publication)
    return publication


def publication_payload(publication: CreationPublication) -> dict:
    """返回稳定的 API 字段，避免直接暴露 ORM 对象。"""
    return {
        "id": publication.id,
        "creation_id": publication.creation_id,
        "platform": publication.platform,
        "operation": publication.operation,
        "status": publication.status,
        "external_id": publication.external_id,
        "external_url": publication.external_url,
        "request_key": publication.request_key,
        "error_message": publication.error_message,
        "started_at": publication.started_at,
        "finished_at": publication.finished_at,
        "created_at": publication.created_at,
        "updated_at": publication.updated_at,
    }

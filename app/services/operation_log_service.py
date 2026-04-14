from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OperationLog

logger = logging.getLogger(__name__)


async def write_operation_log(
    db: AsyncSession,
    *,
    user_id: int | None,
    username: str,
    action_type: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict | str | None = None,
    ip_address: str | None = None,
) -> None:
    try:
        log = OperationLog(
            user_id=user_id,
            username=username,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail or {},
            ip_address=ip_address,
        )
        db.add(log)
        await db.commit()
    except Exception:
        logger.exception("Failed to write operation log")
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.operation_log_service import write_operation_log as _write_operation_log


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
    await _write_operation_log(
        db,
        user_id=user_id,
        username=username,
        action_type=action_type,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        ip_address=ip_address,
    )

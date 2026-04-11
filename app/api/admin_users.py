"""Admin API: user management, quotas, batch assignments, operation logs."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_auth
from app.core.auth import require_admin, require_operator_access
from app.db.models import AppUser, BatchAssignment, OperationLog, UserQuota

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])
operator_router = APIRouter(
    prefix="/api/operator",
    tags=["operator"],
    dependencies=[Depends(require_operator_access)],
)

VALID_ROLES = {"admin", "operator", "searcher"}


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: int
    username: str
    display_name: str | None
    role: str
    status: str
    is_admin: bool
    created_at: datetime
    quota: "QuotaOut | None" = None

    class Config:
        from_attributes = True


class QuotaOut(BaseModel):
    user_id: int
    quota_per_import: int
    quota_total: int
    quota_used: int
    quota_remaining: int
    reset_at: datetime | None

    class Config:
        from_attributes = True


class QuotaUpdate(BaseModel):
    quota_per_import: int = Field(ge=1, le=10000)
    quota_total: int = Field(ge=1, le=1000000)


class RoleUpdate(BaseModel):
    role: str


class AssignmentCreate(BaseModel):
    batch_id: str
    operator_id: int
    file_count: int = 0
    note: str | None = None


class AssignmentOut(BaseModel):
    id: int
    batch_id: str
    admin_id: int
    operator_id: int
    operator_name: str = ""
    file_count: int
    note: str | None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class LogOut(BaseModel):
    id: int
    user_id: int | None
    username: str
    action_type: str
    resource_type: str | None
    resource_id: str | None
    detail: dict
    ip_address: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Helper: ensure quota row exists ──────────────────────────────────────────

async def _ensure_quota(db: AsyncSession, user_id: int) -> UserQuota:
    q = (await db.execute(select(UserQuota).where(UserQuota.user_id == user_id))).scalar_one_or_none()
    if not q:
        try:
            q = UserQuota(user_id=user_id)
            db.add(q)
            await db.commit()
            await db.refresh(q)
        except Exception:
            await db.rollback()
            q = (await db.execute(select(UserQuota).where(UserQuota.user_id == user_id))).scalar_one()
    return q


def _quota_out(q: UserQuota) -> QuotaOut:
    remaining = max(0, q.quota_total - q.quota_used)
    return QuotaOut(
        user_id=q.user_id,
        quota_per_import=q.quota_per_import,
        quota_total=q.quota_total,
        quota_used=q.quota_used,
        quota_remaining=remaining,
        reset_at=q.reset_at,
    )


# ── Admin: user list ──────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    _: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    role: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
) -> dict[str, Any]:
    stmt = select(AppUser).order_by(AppUser.created_at.desc())
    if role:
        stmt = stmt.where(AppUser.role == role)
    if status_filter:
        stmt = stmt.where(AppUser.status == status_filter)
    users = (await db.execute(stmt)).scalars().all()

    items = []
    for u in users:
        q = (await db.execute(select(UserQuota).where(UserQuota.user_id == u.id))).scalar_one_or_none()
        items.append({
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "role": u.role,
            "status": u.status,
            "is_admin": u.is_admin,
            "created_at": u.created_at.isoformat(),
            "quota": _quota_out(q).model_dump() if q else None,
        })
    return {"items": items, "total": len(items)}


# ── Admin: update user role ───────────────────────────────────────────────────

@router.put("/users/{user_id}/role")
async def set_user_role(
    user_id: int,
    body: RoleUpdate,
    request: Request,
    current: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of {VALID_ROLES}")
    user = await db.get(AppUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    old_role = user.role
    user.role = body.role
    user.is_admin = body.role == "admin"
    await db.commit()
    await _write_log(db, current, request, "set_role", "user", str(user_id),
                     {"old_role": old_role, "new_role": body.role, "target_user": user.username})
    return {"id": user_id, "role": user.role}


# ── Admin: update user display_name ──────────────────────────────────────────

@router.put("/users/{user_id}/display-name")
async def set_display_name(
    user_id: int,
    body: dict,
    current: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await db.get(AppUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.display_name = (body.get("display_name") or "").strip() or None
    await db.commit()
    return {"id": user_id, "display_name": user.display_name}


# ── Admin: quota management ───────────────────────────────────────────────────

@router.get("/users/{user_id}/quota")
async def get_quota(
    user_id: int,
    _: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    q = await _ensure_quota(db, user_id)
    return _quota_out(q).model_dump()


@router.put("/users/{user_id}/quota")
async def update_quota(
    user_id: int,
    body: QuotaUpdate,
    request: Request,
    current: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await db.get(AppUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    q = await _ensure_quota(db, user_id)
    q.quota_per_import = body.quota_per_import
    q.quota_total = body.quota_total
    await db.commit()
    await db.refresh(q)
    await _write_log(db, current, request, "update_quota", "user", str(user_id),
                     {"per_import": body.quota_per_import, "total": body.quota_total,
                      "target_user": user.username})
    return _quota_out(q).model_dump()


@router.post("/users/{user_id}/quota/reset")
async def reset_quota(
    user_id: int,
    request: Request,
    current: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await db.get(AppUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    q = await _ensure_quota(db, user_id)
    q.quota_used = 0
    q.reset_at = datetime.utcnow()
    await db.commit()
    await db.refresh(q)
    await _write_log(db, current, request, "reset_quota", "user", str(user_id),
                     {"target_user": user.username})
    return _quota_out(q).model_dump()


# ── Admin: batch assignments ──────────────────────────────────────────────────

@router.get("/assignments")
async def list_assignments(
    _: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    operator_id: int | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    stmt = select(BatchAssignment).order_by(desc(BatchAssignment.created_at)).limit(limit).offset(offset)
    if operator_id:
        stmt = stmt.where(BatchAssignment.operator_id == operator_id)
    if status_filter:
        stmt = stmt.where(BatchAssignment.status == status_filter)
    assignments = (await db.execute(stmt)).scalars().all()

    items = []
    for a in assignments:
        op = await db.get(AppUser, a.operator_id)
        items.append({
            "id": a.id,
            "batch_id": a.batch_id,
            "admin_id": a.admin_id,
            "operator_id": a.operator_id,
            "operator_name": (op.display_name or op.username) if op else str(a.operator_id),
            "file_count": a.file_count,
            "note": a.note,
            "status": a.status,
            "created_at": a.created_at.isoformat(),
        })
    return {"items": items, "total": len(items)}


@router.post("/assignments", status_code=status.HTTP_201_CREATED)
async def create_assignment(
    body: AssignmentCreate,
    request: Request,
    current: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    op = await db.get(AppUser, body.operator_id)
    if not op:
        raise HTTPException(status_code=404, detail="Operator not found.")
    if op.role not in {"operator"}:
        raise HTTPException(status_code=400, detail="Target user is not an operator.")

    assignment = BatchAssignment(
        batch_id=body.batch_id,
        admin_id=current.get("user_id") or 0,
        operator_id=body.operator_id,
        file_count=body.file_count,
        note=body.note,
        status="pending",
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    await _write_log(db, current, request, "assign_batch", "batch", body.batch_id,
                     {"operator_id": body.operator_id, "operator_name": op.username,
                      "file_count": body.file_count})
    return {"id": assignment.id, "batch_id": assignment.batch_id, "status": assignment.status}


@router.put("/assignments/{assignment_id}/status")
async def update_assignment_status(
    assignment_id: int,
    body: dict,
    current: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    a = await db.get(BatchAssignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    new_status = body.get("status", "")
    if new_status not in {"pending", "processing", "done", "cancelled"}:
        raise HTTPException(status_code=400, detail="Invalid status value.")
    a.status = new_status
    await db.commit()
    return {"id": a.id, "status": a.status}


# ── Admin: operation logs ─────────────────────────────────────────────────────

@router.get("/operation-logs")
async def list_operation_logs(
    _: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    user_id: int | None = Query(None),
    action_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    stmt = select(OperationLog).order_by(desc(OperationLog.created_at)).limit(limit).offset(offset)
    if user_id:
        stmt = stmt.where(OperationLog.user_id == user_id)
    if action_type:
        stmt = stmt.where(OperationLog.action_type == action_type)
    logs = (await db.execute(stmt)).scalars().all()
    items = [
        {
            "id": lo.id,
            "user_id": lo.user_id,
            "username": lo.username,
            "action_type": lo.action_type,
            "resource_type": lo.resource_type,
            "resource_id": lo.resource_id,
            "detail": lo.detail,
            "ip_address": lo.ip_address,
            "created_at": lo.created_at.isoformat(),
        }
        for lo in logs
    ]
    return {"items": items, "total": len(items)}


# ── Operator: my quota ────────────────────────────────────────────────────────

@operator_router.get("/my-quota")
async def get_my_quota(
    current: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    uid = current.get("user_id")
    if not uid:
        return {"quota_per_import": 9999, "quota_total": 9999, "quota_used": 0, "quota_remaining": 9999}
    q = await _ensure_quota(db, uid)
    return _quota_out(q).model_dump()


# ── Operator: my assignments ──────────────────────────────────────────────────

@operator_router.get("/my-assignments")
async def get_my_assignments(
    current: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, alias="status"),
) -> dict[str, Any]:
    uid = current.get("user_id")
    if not uid:
        return {"items": [], "total": 0}
    stmt = (
        select(BatchAssignment)
        .where(BatchAssignment.operator_id == uid)
        .order_by(desc(BatchAssignment.created_at))
    )
    if status_filter:
        stmt = stmt.where(BatchAssignment.status == status_filter)
    assignments = (await db.execute(stmt)).scalars().all()
    return {
        "items": [
            {
                "id": a.id,
                "batch_id": a.batch_id,
                "file_count": a.file_count,
                "note": a.note,
                "status": a.status,
                "created_at": a.created_at.isoformat(),
            }
            for a in assignments
        ],
        "total": len(assignments),
    }


# ── Operator: consume quota (called internally after successful upload) ───────

@operator_router.post("/my-quota/consume")
async def consume_quota(
    body: dict,
    request: Request,
    current: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    uid = current.get("user_id")
    count = int(body.get("count", 0))
    if not uid or count <= 0:
        return {"ok": True}

    q = await _ensure_quota(db, uid)
    if q.quota_used + count > q.quota_total:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"超出总配额限制（已用 {q.quota_used}，总额 {q.quota_total}）",
        )
    q.quota_used += count
    await db.commit()
    await _write_log(db, current, request, "import_files", "batch",
                     body.get("batch_id"), {"file_count": count})
    return _quota_out(q).model_dump()


# ── Internal: write operation log ─────────────────────────────────────────────

async def _write_log(
    db: AsyncSession,
    current: dict,
    request: Request | None,
    action_type: str,
    resource_type: str | None,
    resource_id: str | None,
    detail: dict | None = None,
) -> None:
    try:
        ip = None
        if request:
            forwarded = request.headers.get("x-forwarded-for")
            ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
        log = OperationLog(
            user_id=current.get("user_id"),
            username=current.get("username") or "",
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail or {},
            ip_address=ip,
        )
        db.add(log)
        await db.commit()
    except Exception:
        logger.exception("Failed to write operation log")


async def write_operation_log(
    db: AsyncSession,
    *,
    user_id: int | None,
    username: str,
    action_type: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Public helper for other modules to record audit events."""
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

"""租户管理 API — 仅超级管理员可调用（公开列表端点除外）。"""

from __future__ import annotations

import re
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.auth import require_platform_admin
from app.db.models import AppUser, Tenant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/tenants", tags=["tenants"])

# 注册页用的公开只读路由（不需要认证）
public_router = APIRouter(prefix="/api/tenants", tags=["tenants-public"])

_TENANT_ID_RE = re.compile(r"^[a-z0-9_-]{2,64}$")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    id: str = Field(..., min_length=2, max_length=64, description="租户唯一标识（小写字母/数字/下划线/横线）")
    name: str = Field(..., min_length=1, max_length=120, description="显示名称")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not _TENANT_ID_RE.match(v):
            raise ValueError("tenant id 只允许小写字母、数字、下划线和横线，长度 2-64")
        return v


class TenantUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    status: str | None = Field(None, pattern="^(active|disabled)$")


class TenantOut(BaseModel):
    id: str
    name: str
    status: str
    created_at: datetime
    user_count: int = 0

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_tenants(
    _: dict = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    tenants = (await db.execute(select(Tenant).order_by(Tenant.created_at))).scalars().all()
    result = []
    for t in tenants:
        count = len((await db.execute(
            select(AppUser).where(AppUser.tenant_id == t.id)
        )).scalars().all())
        result.append({
            "id": t.id,
            "name": t.name,
            "status": t.status,
            "created_at": t.created_at.isoformat(),
            "user_count": count,
        })
    return {"items": result, "total": len(result)}


@router.post("", status_code=201)
async def create_tenant(
    body: TenantCreate,
    _: dict = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    existing = await db.get(Tenant, body.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"租户 '{body.id}' 已存在。")
    tenant = Tenant(id=body.id, name=body.name)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return {"id": tenant.id, "name": tenant.name, "status": tenant.status}


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    _: dict = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在。")
    count = len((await db.execute(
        select(AppUser).where(AppUser.tenant_id == tenant_id)
    )).scalars().all())
    return {
        "id": tenant.id,
        "name": tenant.name,
        "status": tenant.status,
        "created_at": tenant.created_at.isoformat(),
        "user_count": count,
    }


@router.patch("/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    body: TenantUpdate,
    _: dict = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在。")
    if body.name is not None:
        tenant.name = body.name
    if body.status is not None:
        tenant.status = body.status
    await db.commit()
    await db.refresh(tenant)
    return {"id": tenant.id, "name": tenant.name, "status": tenant.status}


@router.post("/{tenant_id}/assign-user")
async def assign_user_to_tenant(
    tenant_id: str,
    body: dict,
    _: dict = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """将用户移入指定租户（admin only）。"""
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在。")
    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id 必填。")
    user = await db.get(AppUser, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在。")
    user.tenant_id = tenant_id
    await db.commit()
    return {"ok": True, "user_id": user.id, "tenant_id": tenant_id}


# ── Public endpoint (no auth) ────────────────────────────────────────────────

@public_router.get("")
async def list_tenants_public(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """仅返回启用状态的租户列表，供注册页使用（无需登录）。"""
    tenants = (await db.execute(
        select(Tenant).where(Tenant.status == "active").order_by(Tenant.name)
    )).scalars().all()
    return {
        "items": [{"id": t.id, "name": t.name} for t in tenants]
    }

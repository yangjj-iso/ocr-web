"""Authentication domain operations."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    AUTH_ENABLED,
    AUTH_USERNAME,
    get_authenticated_user,
    hash_password,
    require_admin,
    set_auth_cookie,
    validate_credentials,
    verify_password,
)
from app.db.models import AppUser


def ensure_auth_enabled() -> None:
    if AUTH_ENABLED:
        return
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Auth is disabled.")


async def get_user_by_username(db: AsyncSession, username: str) -> AppUser | None:
    return (
        await db.execute(select(AppUser).where(AppUser.username == username))
    ).scalar_one_or_none()


async def register_pending_user(db: AsyncSession, username: str, password: str) -> AppUser:
    normalized_username = username.strip()
    if not normalized_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be empty.",
        )
    if normalized_username.lower() == AUTH_USERNAME.lower():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is reserved.",
        )

    existing = await get_user_by_username(db, normalized_username)
    if existing:
        if existing.status == "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This account is pending approval.",
            )
        if existing.status == "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This username is already in use.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account has been rejected.",
        )

    user = AppUser(
        username=normalized_username,
        password_hash=hash_password(password),
        status="pending",
        is_admin=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_application_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> AppUser:
    user = await get_user_by_username(db, username.strip())
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Basic"},
        )

    if user.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending approval. Please contact administrator.",
        )
    if user.status == "rejected":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account rejected. Please contact administrator.",
        )
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is unavailable.",
        )
    return user


def authenticate_env_admin(username: str, password: str) -> bool:
    return validate_credentials(username.strip(), password or "")


def write_auth_cookie_for_user(response, user: AppUser) -> None:
    set_auth_cookie(
        response,
        user.username,
        user_id=user.id,
        is_admin=bool(user.is_admin),
        user_status=user.status,
    )


def write_auth_cookie_for_admin(response, username: str) -> None:
    set_auth_cookie(response, username, is_admin=True, user_status="active")


async def list_pending_users(db: AsyncSession) -> list[AppUser]:
    return (
        await db.execute(
            select(AppUser).where(AppUser.status == "pending").order_by(AppUser.created_at.desc())
        )
    ).scalars().all()


async def change_user_status(db: AsyncSession, user_id: int, status_value: str) -> AppUser:
    user = await db.get(AppUser, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.status = status_value
    await db.commit()
    await db.refresh(user)
    return user


__all__ = [
    "authenticate_application_user",
    "authenticate_env_admin",
    "change_user_status",
    "ensure_auth_enabled",
    "get_authenticated_user",
    "list_pending_users",
    "register_pending_user",
    "require_admin",
    "write_auth_cookie_for_admin",
    "write_auth_cookie_for_user",
]

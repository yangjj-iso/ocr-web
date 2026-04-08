"""Authentication routes."""

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.workflows.auth import (
    approve_user,
    list_pending_users,
    login_user,
    register_user,
    reject_user,
)
from app.core.auth import clear_auth_cookie, get_authenticated_user
from app.db.database import get_db
from app.domains.auth import auth_service
from config import AUTH_ENABLED, AUTH_USERNAME


router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginBody(BaseModel):
    username: str
    password: str


class RegisterBody(BaseModel):
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=6, max_length=200)


@router.get("/me")
async def auth_me(request: Request):
    user = get_authenticated_user(request)
    return {
        "enabled": AUTH_ENABLED,
        "authenticated": bool(user),
        "username": user["username"] if user else None,
        "is_admin": bool(user.get("is_admin")) if user else False,
        "user_status": user.get("user_status") if user else None,
        "default_username": AUTH_USERNAME if AUTH_ENABLED else None,
    }


@router.post("/register")
async def auth_register(body: RegisterBody, db: AsyncSession = Depends(get_db)):
    return await register_user(username=body.username, password=body.password, db=db)


@router.post("/login")
async def auth_login(body: LoginBody, response: Response, db: AsyncSession = Depends(get_db)):
    payload = await login_user(
        username=body.username,
        password=body.password,
        response=response,
        db=db,
    )
    if payload is None:
        response.status_code = status.HTTP_204_NO_CONTENT
        return
    return payload


@router.post("/logout")
async def auth_logout(response: Response):
    clear_auth_cookie(response)
    return {"authenticated": False}


@router.get("/pending-users")
async def auth_pending_users(request: Request, db: AsyncSession = Depends(get_db)):
    auth_service.ensure_auth_enabled()
    auth_service.require_admin(request)
    return await list_pending_users(db=db)


@router.post("/users/{user_id}/approve")
async def auth_approve_user(user_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    auth_service.ensure_auth_enabled()
    auth_service.require_admin(request)
    return await approve_user(user_id=user_id, db=db)


@router.post("/users/{user_id}/reject")
async def auth_reject_user(user_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    auth_service.ensure_auth_enabled()
    auth_service.require_admin(request)
    return await reject_user(user_id=user_id, db=db)

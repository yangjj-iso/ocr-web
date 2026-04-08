"""Authentication orchestration workflows."""

from __future__ import annotations

from app.domains.auth import auth_service


async def register_user(*, username: str, password: str, db) -> dict:
    auth_service.ensure_auth_enabled()
    await auth_service.register_pending_user(db, username, password)
    return {
        "registered": True,
        "status": "pending",
        "message": "Registration submitted. Please wait for administrator approval.",
    }


async def login_user(*, username: str, password: str, response, db) -> dict | None:
    if not auth_service.AUTH_ENABLED:
        response.status_code = 204
        return None

    normalized_username = username.strip()
    normalized_password = password or ""
    if not normalized_username or not normalized_password:
        raise auth_service.HTTPException(status_code=400, detail="Username and password are required.")

    if auth_service.authenticate_env_admin(normalized_username, normalized_password):
        auth_service.write_auth_cookie_for_admin(response, normalized_username)
        return {
            "authenticated": True,
            "username": normalized_username,
            "is_admin": True,
            "user_status": "active",
        }

    user = await auth_service.authenticate_application_user(db, normalized_username, normalized_password)
    auth_service.write_auth_cookie_for_user(response, user)
    return {
        "authenticated": True,
        "username": user.username,
        "is_admin": bool(user.is_admin),
        "user_status": user.status,
    }


async def list_pending_users(*, db) -> dict:
    users = await auth_service.list_pending_users(db)
    return {
        "items": [
            {
                "id": user.id,
                "username": user.username,
                "status": user.status,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
            for user in users
        ]
    }


async def approve_user(*, user_id: int, db) -> dict:
    user = await auth_service.change_user_status(db, user_id, "active")
    return {"id": user.id, "username": user.username, "status": user.status}


async def reject_user(*, user_id: int, db) -> dict:
    user = await auth_service.change_user_status(db, user_id, "rejected")
    return {"id": user.id, "username": user.username, "status": user.status}

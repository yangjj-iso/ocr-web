import base64
import hashlib
import hmac
import json
import os
import time
from secrets import compare_digest
from typing import Any

from fastapi import HTTPException, Request, Response, status

from config import (
    AUTH_COOKIE_NAME,
    AUTH_COOKIE_SECURE,
    AUTH_COOKIE_SAMESITE,
    AUTH_ENABLED,
    AUTH_PASSWORD,
    AUTH_SECRET,
    AUTH_SESSION_TTL,
    AUTH_USERNAME,
)


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}")


def validate_credentials(username: str, password: str) -> bool:
    if not AUTH_ENABLED:
        return True
    return compare_digest(username, AUTH_USERNAME) and compare_digest(password, AUTH_PASSWORD)


def hash_password(password: str, iterations: int = 240_000) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        algorithm, iterations_raw, salt_raw, expected_raw = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = _b64decode(salt_raw)
        expected = _b64decode(expected_raw)
    except (ValueError, TypeError):
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return compare_digest(candidate, expected)


def create_session_token(
    username: str,
    ttl: int = AUTH_SESSION_TTL,
    *,
    user_id: int | None = None,
    is_admin: bool = False,
    user_status: str = "active",
    role: str = "member",
    capabilities: str = "",
    tenant_id: str = "default",
) -> str:
    payload = {
        "sub": username,
        "exp": int(time.time()) + ttl,
        "uid": user_id,
        "is_admin": bool(is_admin),
        "user_status": user_status or "active",
        "role": role or "member",
        "capabilities": capabilities or "",
        "tenant_id": tenant_id or "default",
    }
    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_encoded = _b64encode(payload_raw)
    signature = hmac.new(
        AUTH_SECRET.encode("utf-8"),
        payload_encoded.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_encoded}.{signature}"


def verify_session_token(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        payload_encoded, signature = token.split(".", 1)
    except ValueError:
        return None

    expected = hmac.new(
        AUTH_SECRET.encode("utf-8"),
        payload_encoded.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not compare_digest(signature, expected):
        return None

    try:
        payload = json.loads(_b64decode(payload_encoded).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None

    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload


def _extract_basic_credentials(request: Request) -> tuple[str, str] | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return None
    try:
        decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
        username, password = decoded.split(":", 1)
    except (ValueError, UnicodeDecodeError):
        return None
    return username, password


def get_authenticated_user(request: Request) -> dict[str, Any] | None:
    if not AUTH_ENABLED:
        return {"username": AUTH_USERNAME, "is_admin": True, "user_status": "active", "user_id": None, "role": "admin", "capabilities": "", "tenant_id": "default"}

    payload = verify_session_token(request.cookies.get(AUTH_COOKIE_NAME))
    if payload:
        user_status = str(payload.get("user_status") or "active")
        if user_status != "active":
            return None
        return {
            "username": str(payload["sub"]),
            "is_admin": bool(payload.get("is_admin")),
            "user_status": user_status,
            "user_id": payload.get("uid"),
            "role": str(payload.get("role") or "member"),
            "capabilities": str(payload.get("capabilities") or ""),
            "tenant_id": str(payload.get("tenant_id") or "default"),
        }

    basic = _extract_basic_credentials(request)
    if basic and validate_credentials(*basic):
        return {"username": basic[0], "is_admin": True, "user_status": "active", "user_id": None, "role": "admin", "capabilities": "", "tenant_id": "default"}
    return None


def require_auth(request: Request) -> dict[str, Any]:
    user = get_authenticated_user(request)
    if user:
        return user
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


def require_admin(request: Request) -> dict[str, Any]:
    """Allow company admin (is_admin=True) or tenant_admin."""
    user = require_auth(request)
    if user.get("is_admin") or effective_role(user) == "tenant_admin":
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permission required.")


def require_platform_admin(request: Request) -> dict[str, Any]:
    """Allow only true company admin (is_admin=True). Tenant admins are NOT allowed."""
    user = require_auth(request)
    if user.get("is_admin"):
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin permission required.")


def effective_role(user: dict[str, Any] | None) -> str:
    if not user:
        return ""
    if user.get("is_admin"):
        return "admin"
    return str(user.get("role") or "member").strip().lower()


def _has_capability(user: dict[str, Any], cap: str) -> bool:
    """Return True if user has the given capability tag, or is admin/tenant_admin."""
    role = effective_role(user)
    if role in {"admin", "tenant_admin"}:
        return True
    caps = str(user.get("capabilities") or "")
    return cap in caps.split(",")


def require_operator_access(request: Request) -> dict[str, Any]:
    """Allow admin, tenant_admin, or member with 'operator' capability."""
    user = require_auth(request)
    if _has_capability(user, "operator"):
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator permission required.")


def require_searcher_access(request: Request) -> dict[str, Any]:
    """Allow admin, tenant_admin, or member with 'searcher' capability."""
    user = require_auth(request)
    if _has_capability(user, "searcher"):
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Searcher permission required.")


def require_tenant_admin_access(request: Request) -> dict[str, Any]:
    """Allow company admin or tenant_admin; block plain member roles."""
    user = require_auth(request)
    if effective_role(user) in {"admin", "tenant_admin"}:
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin permission required.")


def set_auth_cookie(
    response: Response,
    username: str,
    *,
    user_id: int | None = None,
    is_admin: bool = False,
    user_status: str = "active",
    role: str = "operator",
    capabilities: str = "",
    tenant_id: str = "default",
) -> None:
    response.set_cookie(
        AUTH_COOKIE_NAME,
        create_session_token(
            username,
            user_id=user_id,
            is_admin=is_admin,
            user_status=user_status,
            role=role,
            capabilities=capabilities,
            tenant_id=tenant_id,
        ),
        max_age=AUTH_SESSION_TTL,
        httponly=True,
        samesite=AUTH_COOKIE_SAMESITE,
        secure=AUTH_COOKIE_SECURE,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        AUTH_COOKIE_NAME,
        path="/",
        samesite=AUTH_COOKIE_SAMESITE,
        secure=AUTH_COOKIE_SECURE,
    )

"""Authentication domain."""

from . import auth_service
from .auth_service import get_authenticated_user, require_admin

__all__ = ["auth_service", "get_authenticated_user", "require_admin"]

"""JWT authentication helpers.

Tokens contain user_id, tenant_id, and role. Production systems should load
JWT_SECRET from a secret manager — never commit a real secret.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import Settings
from app.core.exceptions import AuthError


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    role: str
    username: str = ""


def create_access_token(principal: Principal, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": principal.user_id,
        "tenant_id": principal.tenant_id,
        "role": principal.role,
        "username": principal.username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> Principal:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid token") from exc

    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    role = payload.get("role")
    if not user_id or not tenant_id or not role:
        raise AuthError("Token missing required claims")
    return Principal(
        user_id=str(user_id),
        tenant_id=str(tenant_id),
        role=str(role),
        username=str(payload.get("username") or ""),
    )


def authorize_tenant(principal: Principal, requested_tenant_id: str) -> None:
    """Authenticated tenant must equal the requested tenant.

    Security is never degraded. A token for tenant-a cannot query tenant-b.
    """
    from app.core.exceptions import ForbiddenError

    if principal.tenant_id != requested_tenant_id:
        raise ForbiddenError("Token tenant does not match requested tenant")

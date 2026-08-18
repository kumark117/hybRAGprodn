from __future__ import annotations

from fastapi import Depends, Header, Request

from app.container import AppContainer
from app.core.exceptions import AuthError, ForbiddenError
from app.core.security import Principal, authorize_tenant, decode_access_token
from app.observability.timing import emit_simple


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


async def get_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    container: AppContainer = Depends(get_container),
) -> Principal:
    request_id = getattr(request.state, "request_id", "")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    principal = decode_access_token(token, container.settings)
    await emit_simple(
        container.base_sink(),
        request_id=request_id,
        stage="AUTH",
        event="jwt_validated",
        message="JWT validated",
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
    )
    await container.rate_limiter.check(
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        request_id=request_id,
    )
    request.state.principal = principal
    return principal


def require_tenant(requested_tenant_id: str, principal: Principal) -> None:
    authorize_tenant(principal, requested_tenant_id)

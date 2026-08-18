from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_container
from app.container import AppContainer
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, container: AppContainer = Depends(get_container)):
    token, principal = container.auth.login(body.username, body.password)
    return TokenResponse(
        access_token=token,
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        role=principal.role,
        expires_in_minutes=container.settings.JWT_EXPIRE_MINUTES,
    )

"""JWT login against configured demo users. Replace with IdP in production."""

from __future__ import annotations

from app.core.config import Settings
from app.core.exceptions import AuthError
from app.core.security import Principal, create_access_token


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._users = {row["username"]: row for row in settings.demo_user_records()}

    def login(self, username: str, password: str) -> tuple[str, Principal]:
        record = self._users.get(username)
        if record is None or record["password"] != password:
            raise AuthError("Invalid username or password")
        principal = Principal(
            user_id=record["user_id"],
            tenant_id=record["tenant_id"],
            role=record["role"],
            username=username,
        )
        token = create_access_token(principal, self.settings)
        return token, principal

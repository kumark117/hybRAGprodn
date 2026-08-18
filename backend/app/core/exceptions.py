"""Centralized application exceptions.

API clients receive a stable error envelope. Internal stack traces stay in
structured logs and never leak to the browser.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ValidationAppError(AppError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("VALIDATION_ERROR", message, status_code=400, details=details)


class AuthError(AppError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__("UNAUTHORIZED", message, status_code=401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Not authorized for this tenant") -> None:
        super().__init__("FORBIDDEN", message, status_code=403)


class RateLimitError(AppError):
    def __init__(self, message: str = "Too many requests") -> None:
        super().__init__("RATE_LIMITED", message, status_code=429)


class NotFoundError(AppError):
    def __init__(self, message: str, code: str = "NOT_FOUND") -> None:
        super().__init__(code, message, status_code=404)


class RetryableProviderError(AppError):
    def __init__(self, code: str, message: str, *, provider: str, status: int | None = None) -> None:
        super().__init__(
            code,
            message,
            status_code=503,
            details={"provider": provider, "upstream_status": status},
        )
        self.provider = provider
        self.upstream_status = status


class PermanentProviderError(AppError):
    def __init__(self, code: str, message: str, *, provider: str, status: int | None = None) -> None:
        super().__init__(
            code,
            message,
            status_code=400 if status in {400, 401, 403} else 502,
            details={"provider": provider, "upstream_status": status},
        )


class CircuitOpenError(AppError):
    def __init__(self, name: str) -> None:
        super().__init__(
            "CIRCUIT_OPEN",
            f"Circuit breaker '{name}' is open",
            status_code=503,
            details={"circuit": name},
        )


class VectorStoreUnavailable(RetryableProviderError):
    def __init__(self, message: str = "Vector retrieval is temporarily unavailable") -> None:
        super().__init__("VECTOR_STORE_UNAVAILABLE", message, provider="pinecone")


class LLMUnavailable(RetryableProviderError):
    def __init__(self, message: str = "Language model is temporarily unavailable") -> None:
        super().__init__("LLM_UNAVAILABLE", message, provider="llm")

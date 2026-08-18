"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import router as v1_router
from app.container import build_container
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger
from app.observability.middleware import RequestContextMiddleware
from app.observability.tracing import configure_tracing, shutdown_tracing
from app.schemas.common import ErrorBody, ErrorResponse

logger = get_logger("rag.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    get_settings.cache_clear()
    settings = get_settings()
    configure_logging(settings)
    configure_tracing(settings)
    app.state.container = await build_container(settings)
    logger.info("startup", env=settings.APP_ENV, fake_providers=settings.USE_FAKE_PROVIDERS)
    try:
        yield
    finally:
        redis = getattr(app.state.container, "redis", None)
        if redis is not None:
            await redis.aclose()
        shutdown_tracing()
        logger.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Hybrid RAG Production API",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-Trace-ID"],
    )
    application.include_router(v1_router)

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "")
        logger.warning("app_error", code=exc.code, status=exc.status_code, request_id=request_id)
        body = ErrorResponse(
            error=ErrorBody(
                code=exc.code,
                message=exc.message,
                request_id=request_id,
                details=exc.details if settings.is_development else {},
            )
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @application.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "")
        logger.error("unhandled_error", error_type=type(exc).__name__, request_id=request_id)
        body = ErrorResponse(
            error=ErrorBody(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred",
                request_id=request_id,
            )
        )
        return JSONResponse(status_code=500, content=body.model_dump())

    return application


app = create_app()

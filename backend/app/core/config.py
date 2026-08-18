"""Application settings loaded from environment variables.

Secrets never have production defaults. Demo JWT/users exist only so the
learning project can boot locally without a secrets manager.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    APP_ENV: str = "development"
    APP_NAME: str = "rag-production"
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    USE_FAKE_PROVIDERS: bool = True

    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_FALLBACK_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    PINECONE_API_KEY: str = ""
    PINECONE_INDEX: str = "rag-hybrid"
    PINECONE_CLOUD: str = "aws"
    PINECONE_REGION: str = "us-east-1"

    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_FAIL_OPEN: bool = True
    CACHE_TTL_SECONDS: int = 600
    SEMANTIC_CACHE_ENABLED: bool = False
    SEMANTIC_CACHE_THRESHOLD: float = 0.92

    JWT_SECRET: str = "change-me-in-production-use-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    DEMO_USERS: str = (
        "analyst:analystpass:tenant-a:analyst,"
        "admin:adminpass:tenant-a:admin,"
        "other:otherpass:tenant-b:analyst"
    )

    VECTOR_TOP_K: int = 20
    BM25_TOP_K: int = 20
    RERANK_TOP_K: int = 12
    RRF_K: int = 60
    MAX_CONTEXT_TOKENS: int = 3500
    MAX_CHUNKS_PER_SOURCE: int = 3

    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64

    MAX_RETRIES: int = 3
    RETRY_BASE_SECONDS: float = 0.4
    RETRY_MAX_SECONDS: float = 8.0

    LLM_TIMEOUT_SECONDS: float = 30.0
    EMBEDDING_TIMEOUT_SECONDS: float = 15.0
    PINECONE_TIMEOUT_SECONDS: float = 8.0
    RERANKER_TIMEOUT_SECONDS: float = 12.0
    REDIS_TIMEOUT_SECONDS: float = 2.0

    MAX_QUERY_LENGTH: int = 2000
    MAX_DOCUMENT_SIZE: int = 200_000

    MAX_LLM_CONCURRENCY: int = 8
    MAX_EMBEDDING_CONCURRENCY: int = 8
    MAX_RERANK_CONCURRENCY: int = 4

    RATE_LIMIT_PER_USER_PER_MINUTE: int = 60
    RATE_LIMIT_PER_TENANT_PER_MINUTE: int = 300

    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"

    PROMPT_VERSION: str = "v2"
    INDEX_VERSION: str = "v1"
    EMBEDDING_MODEL_VERSION: str = "v1"

    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4318"
    OTEL_SERVICE_NAME: str = "rag-backend"

    SSE_HEARTBEAT_SECONDS: float = 15.0
    SSE_QUEUE_MAX_SIZE: int = 500

    CIRCUIT_FAILURE_THRESHOLD: int = 5
    CIRCUIT_RESET_SECONDS: float = 30.0

    REWRITE_ENABLED: bool = True

    EMBEDDING_DIMENSION: int = 1536

    @field_validator("CORS_ALLOWED_ORIGINS")
    @classmethod
    def reject_star_in_production(cls, value: str, info) -> str:  # noqa: ARG003
        return value

    @property
    def cors_origins(self) -> list[str]:
        origins = [item.strip() for item in self.CORS_ALLOWED_ORIGINS.split(",") if item.strip()]
        if self.is_production and origins == ["*"]:
            raise ValueError("CORS_ALLOWED_ORIGINS must not be '*' in production")
        return origins

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() in {"prod", "production"}

    @property
    def is_development(self) -> bool:
        return not self.is_production

    def demo_user_records(self) -> list[dict[str, str]]:
        users: list[dict[str, str]] = []
        for raw in self.DEMO_USERS.split(","):
            parts = raw.strip().split(":")
            if len(parts) != 4:
                continue
            username, password, tenant_id, role = parts
            users.append(
                {
                    "username": username,
                    "password": password,
                    "tenant_id": tenant_id,
                    "role": role,
                    "user_id": f"user-{username}",
                }
            )
        return users


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

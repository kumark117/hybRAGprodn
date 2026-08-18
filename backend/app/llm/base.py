"""LLM provider interfaces."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class LLMResult:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    fallback_used: bool = False
    time_to_first_token_ms: float | None = None


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model: str

    async def generate(self, *, system: str, user: str) -> LLMResult: ...

    def stream(self, *, system: str, user: str) -> AsyncIterator[str]: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    model: str
    dimension: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

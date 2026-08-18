"""OpenAI-compatible chat and streaming client."""

from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.core.config import Settings
from app.core.exceptions import PermanentProviderError, RetryableProviderError
from app.core.retry import classify_http_status
from app.llm.base import LLMResult


class OpenAIProvider:
    def __init__(self, settings: Settings, *, model: str | None = None, name: str = "openai") -> None:
        self.name = name
        self.model = model or settings.OPENAI_MODEL
        self._timeout = settings.LLM_TIMEOUT_SECONDS
        self._client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY or "missing",
            base_url=settings.OPENAI_BASE_URL,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )

    async def generate(self, *, system: str, user: str) -> LLMResult:
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.1,
            )
        except Exception as exc:
            raise _map_openai_error(exc, self.name) from exc
        choice = response.choices[0].message.content or ""
        usage = response.usage
        return LLMResult(
            text=choice,
            model=self.model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )

    async def stream(self, *, system: str, user: str) -> AsyncIterator[str]:
        try:
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.1,
                stream=True,
            )
        except Exception as exc:
            raise _map_openai_error(exc, self.name) from exc
        async for event in stream:
            delta = event.choices[0].delta.content if event.choices else None
            if delta:
                yield delta


def _map_openai_error(exc: Exception, provider: str) -> Exception:
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    message = "Language model request failed"
    if status:
        return classify_http_status(int(status), provider, message)
    name = type(exc).__name__.lower()
    if "timeout" in name or "connect" in name:
        return RetryableProviderError("PROVIDER_TIMEOUT", message, provider=provider)
    return PermanentProviderError("LLM_ERROR", message, provider=provider)

"""Mock LLM used when no API key is present.

It does not call a vendor. It extracts sentences from retrieved
<untrusted-document> blocks so local demos answer from the indexed corpus
instead of a canned retry paragraph.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator

from app.llm.base import LLMResult

_BLOCK = re.compile(
    r"\[(\d+)\]\s+source=(?P<source>\S+)[^\n]*\n"
    r"<untrusted-document[^>]*>\s*(?P<body>.*?)\s*</untrusted-document>",
    re.DOTALL,
)
_TOKEN = re.compile(r"[a-z0-9]{3,}")
_STOP = {
    "the",
    "and",
    "for",
    "how",
    "does",
    "what",
    "why",
    "with",
    "from",
    "that",
    "this",
    "are",
    "was",
    "system",
    "about",
}


class MockLLMProvider:
    def __init__(self, model: str = "mock-llm") -> None:
        self.name = "mock-llm"
        self.model = model

    async def generate(self, *, system: str, user: str) -> LLMResult:
        text = _synthetic_answer(user)
        return LLMResult(
            text=text,
            model=self.model,
            prompt_tokens=len(user.split()),
            completion_tokens=len(text.split()),
        )

    async def stream(self, *, system: str, user: str) -> AsyncIterator[str]:
        text = _synthetic_answer(user)
        for word in text.split(" "):
            await asyncio.sleep(0)
            yield word + " "


def _synthetic_answer(user: str) -> str:
    question = _question_from_prompt(user)
    blocks = [
        (int(match.group(1)), match.group("source"), match.group("body").strip())
        for match in _BLOCK.finditer(user)
    ]
    if not blocks:
        return "I do not have enough evidence in the retrieved context to answer."

    q_tokens = {t for t in _TOKEN.findall(question.lower()) if t not in _STOP}
    scored: list[tuple[int, int, str, str]] = []
    for citation, source, body in blocks:
        for sentence in _sentences(body):
            overlap = len(q_tokens & set(_TOKEN.findall(sentence.lower())))
            if overlap:
                scored.append((overlap, citation, source, sentence))
    scored.sort(key=lambda item: item[0], reverse=True)

    picked: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    for overlap, citation, source, sentence in scored:
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        picked.append((citation, source, sentence))
        if len(picked) >= 3:
            break

    if not picked:
        citation, source, body = blocks[0]
        preview = " ".join(body.split())[:280]
        return f"Retrieved {source} but could not match the question tightly. Excerpt: {preview} [{citation}]"

    parts: list[str] = []
    used: set[int] = set()
    for citation, _source, sentence in picked:
        cite = f" [{citation}]" if citation not in used else ""
        used.add(citation)
        parts.append(sentence.rstrip(".") + cite)
    return ". ".join(parts) + "."


def _question_from_prompt(user: str) -> str:
    if user.startswith("Question:"):
        rest = user.split("Context:", 1)[0]
        return rest.replace("Question:", "", 1).strip()
    return user


def _sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    return [c.strip() for c in chunks if len(c.strip()) > 40]

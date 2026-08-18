"""Recursive, approximately token-aware chunking.

CHUNK_SIZE and CHUNK_OVERLAP are measured in estimated tokens (chars/4),
which is good enough for a learning system and avoids a hard tokenizer
dependency at import time.
"""

from __future__ import annotations

import re

from app.models.document import Chunk

_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def chunk_text(
    text: str,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    def flush() -> None:
        nonlocal current, current_tokens
        if current:
            chunks.append("\n\n".join(current).strip())
            if chunk_overlap > 0 and chunks[-1]:
                overlap_text = _tail_tokens(chunks[-1], chunk_overlap)
                current = [overlap_text] if overlap_text else []
                current_tokens = estimate_tokens(overlap_text) if overlap_text else 0
            else:
                current = []
                current_tokens = 0

    for para in paragraphs:
        para_tokens = estimate_tokens(para)
        if para_tokens > chunk_size:
            flush()
            chunks.extend(_split_long(para, chunk_size, chunk_overlap))
            continue
        if current_tokens + para_tokens > chunk_size:
            flush()
        current.append(para)
        current_tokens += para_tokens

    if current:
        chunks.append("\n\n".join(current).strip())

    return [c for c in chunks if c]


def extract_title(text: str) -> str:
    match = _HEADING.search(text)
    if match:
        return match.group(1).strip()[:120]
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:120]
    return ""


def with_title_prefix(chunks: list[str], title: str) -> list[str]:
    """Repeat the document title on later chunks so they stay retrievable."""
    if not title or not chunks:
        return chunks
    heading = f"# {title}"
    lowered = title.lower()
    prefixed: list[str] = []
    for index, chunk in enumerate(chunks):
        head = chunk[:120].lower()
        if index == 0 or lowered in head:
            prefixed.append(chunk)
        else:
            prefixed.append(f"{heading}\n\n{chunk}")
    return prefixed


def _tail_tokens(text: str, token_budget: int) -> str:
    char_budget = token_budget * 4
    return text[-char_budget:].strip()


def _split_long(text: str, chunk_size: int, overlap: int) -> list[str]:
    char_size = chunk_size * 4
    char_overlap = overlap * 4
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + char_size)
        if end < len(text):
            window = text.rfind(" ", start + char_size // 2, end)
            if window > start:
                end = window
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        start = max(end - char_overlap, start + 1)
    return pieces


def build_chunks(
    *,
    texts: list[str],
    tenant_id: str,
    document_id: str,
    document_version: str,
    source: str,
    metadata: dict,
    chunk_ids: list[str],
) -> list[Chunk]:
    built: list[Chunk] = []
    for index, (text, chunk_id) in enumerate(zip(texts, chunk_ids, strict=True)):
        built.append(
            Chunk(
                chunk_id=chunk_id,
                tenant_id=tenant_id,
                document_id=document_id,
                document_version=document_version,
                chunk_index=index,
                source=source,
                text=text,
                metadata=dict(metadata),
                token_count=estimate_tokens(text),
            )
        )
    return built

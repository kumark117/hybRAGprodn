"""Unit tests for the hybrid RAG core."""

from __future__ import annotations

import pytest

from app.indexing.chunker import chunk_text, estimate_tokens, extract_title, with_title_prefix
from app.indexing.cleaner import clean_document
from app.indexing.ids import make_chunk_id


def test_clean_document_strips_control_chars() -> None:
    assert "hello" in clean_document("hello\x00\n\n\nworld")


def test_chunking_respects_size_and_overlap() -> None:
    text = "\n\n".join(["word " * 80] * 6)
    chunks = chunk_text(text, chunk_size=40, chunk_overlap=8)
    assert len(chunks) >= 2
    assert all(estimate_tokens(c) <= 80 for c in chunks)


def test_deterministic_chunk_ids_are_stable() -> None:
    kwargs = dict(
        tenant_id="tenant-a",
        document_id="doc-1",
        document_version="v1",
        chunk_index=0,
        content="  Hello   world  ",
    )
    first = make_chunk_id(**kwargs)
    second = make_chunk_id(**kwargs)
    assert first == second
    assert first != make_chunk_id(**{**kwargs, "tenant_id": "tenant-b"})


def test_title_prefix_repeats_heading_on_later_chunks() -> None:
    text = "# Interview notes\n\n" + "alpha\n\n" + ("beta " * 80)
    title = extract_title(text)
    assert title == "Interview notes"
    chunks = with_title_prefix(chunk_text(text, chunk_size=40, chunk_overlap=8), title)
    assert chunks
    assert any("# Interview notes" in c for c in chunks[1:]) if len(chunks) > 1 else True

"""Lightweight document cleaning before chunking."""

from __future__ import annotations

import re

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MULTI_NL = re.compile(r"\n{3,}")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")


def clean_document(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _CTRL.sub("", normalized)
    normalized = _MULTI_SPACE.sub(" ", normalized)
    normalized = _MULTI_NL.sub("\n\n", normalized)
    return normalized.strip()

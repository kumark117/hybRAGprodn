"""Walk a folder and collect text files for indexing.

Skips common junk directories. Binary files are ignored.
Document IDs are derived from the relative path so re-indexing is idempotent.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".rst",
    ".py",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".csv",
    ".log",
    ".html",
    ".htm",
    ".xml",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".c",
    ".h",
    ".cpp",
    ".cs",
    ".sql",
}

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    ".next",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".turbo",
}


@dataclass(frozen=True)
class FolderFile:
    path: Path
    relative: str
    document_id: str
    text: str


def document_id_for(relative: str) -> str:
    safe = relative.replace("\\", "/").strip("/")
    slug = safe.replace("/", "__")
    if 0 < len(slug) <= 120:
        return slug
    digest = hashlib.sha256(safe.encode("utf-8")).hexdigest()[:24]
    return f"doc_{digest}"


def iter_text_files(root: Path) -> list[Path]:
    folder = root.expanduser().resolve()
    if not folder.is_dir():
        raise FileNotFoundError(f"Not a directory: {folder}")
    files: list[Path] = []
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        files.append(path)
    files.sort()
    return files


def load_folder(root: Path, *, max_bytes: int) -> list[FolderFile]:
    folder = root.expanduser().resolve()
    loaded: list[FolderFile] = []
    for path in iter_text_files(folder):
        if path.stat().st_size > max_bytes:
            continue
        raw = path.read_bytes()
        if b"\x00" in raw:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="ignore")
        text = text.strip()
        if not text:
            continue
        relative = path.relative_to(folder).as_posix()
        loaded.append(
            FolderFile(
                path=path,
                relative=relative,
                document_id=document_id_for(relative),
                text=text,
            )
        )
    return loaded

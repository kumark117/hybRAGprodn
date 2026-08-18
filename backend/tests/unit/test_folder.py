from pathlib import Path

from app.indexing.folder import document_id_for, iter_text_files, load_folder


def test_document_id_uses_relative_path() -> None:
    assert document_id_for("guides/retry.md") == "guides__retry.md"


def test_iter_text_files_skips_venv(tmp_path: Path) -> None:
    (tmp_path / "keep.md").write_text("hello retries", encoding="utf-8")
    nested = tmp_path / ".venv" / "lib"
    nested.mkdir(parents=True)
    (nested / "secret.md").write_text("should skip", encoding="utf-8")
    (tmp_path / "image.bin").write_bytes(b"\x00\x01")
    files = iter_text_files(tmp_path)
    assert [p.name for p in files] == ["keep.md"]


def test_load_folder_reads_utf8(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("circuit breaker", encoding="utf-8")
    loaded = load_folder(tmp_path, max_bytes=10_000)
    assert len(loaded) == 1
    assert loaded[0].document_id == "a.txt"
    assert "circuit" in loaded[0].text

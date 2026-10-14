"""Directory listing for the shared file-browser modal."""

from __future__ import annotations

from pathlib import Path

from markstar.domain.filebrowser import BrowserEntry, list_browser_entries


def test_lists_dirs_then_files_alphabetically(tmp_path: Path) -> None:
    (tmp_path / "zeta.md").write_text("z", encoding="utf-8")
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta.md").write_text("b", encoding="utf-8")
    (tmp_path / "middle").mkdir()
    entries = list_browser_entries(tmp_path)
    names = [e.name for e in entries]
    assert names == ["alpha", "middle", "beta.md", "zeta.md"]
    assert entries[0].is_dir is True
    assert entries[2].is_dir is False


def test_skips_hidden_and_ignored_dirs(tmp_path: Path) -> None:
    (tmp_path / ".secret").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "visible").mkdir()
    (tmp_path / ".env").write_text("x", encoding="utf-8")
    (tmp_path / "ok.md").write_text("x", encoding="utf-8")
    names = {e.name for e in list_browser_entries(tmp_path)}
    assert names == {"visible", "ok.md"}


def test_includes_non_markdown_files(tmp_path: Path) -> None:
    (tmp_path / "cover.png").write_bytes(b"\x89PNG")
    (tmp_path / "notes.md").write_text("x", encoding="utf-8")
    names = {e.name for e in list_browser_entries(tmp_path)}
    assert names == {"cover.png", "notes.md"}


def test_parent_entry_when_not_at_root(tmp_path: Path) -> None:
    child = tmp_path / "sub"
    child.mkdir()
    entries = list_browser_entries(child, include_parent=True)
    assert entries[0] == BrowserEntry("..", child.parent.resolve(), True, is_parent=True)


def test_no_parent_entry_at_filesystem_root() -> None:
    entries = list_browser_entries(Path("/"), include_parent=True)
    assert all(not e.is_parent for e in entries)

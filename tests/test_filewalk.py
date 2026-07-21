"""Project file enumeration for quick-open: what gets listed, and the caps."""

from __future__ import annotations

from pathlib import Path

from markstar.domain.filewalk import is_openable, list_project_files


def _tree(root: Path) -> None:
    (root / "chapter.md").write_text("x", encoding="utf-8")
    (root / "notes.txt").write_text("x", encoding="utf-8")
    (root / "cover.png").write_bytes(b"\x89PNG")
    (root / "drafts").mkdir()
    (root / "drafts" / "act-one.md").write_text("x", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "config.md").write_text("x", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "readme.md").write_text("x", encoding="utf-8")
    (root / ".hidden").mkdir()
    (root / ".hidden" / "secret.md").write_text("x", encoding="utf-8")
    (root / ".dotfile.md").write_text("x", encoding="utf-8")


def test_lists_documents_relative_to_root(tmp_path: Path) -> None:
    _tree(tmp_path)
    out = list_project_files(tmp_path)
    assert "chapter.md" in out
    assert "notes.txt" in out
    assert "drafts/act-one.md" in out


def test_skips_non_documents(tmp_path: Path) -> None:
    _tree(tmp_path)
    assert "cover.png" not in list_project_files(tmp_path)


def test_skips_vcs_vendor_and_hidden_dirs(tmp_path: Path) -> None:
    _tree(tmp_path)
    out = list_project_files(tmp_path)
    assert not any(p.startswith((".git/", "node_modules/", ".hidden/")) for p in out)


def test_skips_hidden_files(tmp_path: Path) -> None:
    _tree(tmp_path)
    assert ".dotfile.md" not in list_project_files(tmp_path)


def test_respects_max_files(tmp_path: Path) -> None:
    for i in range(20):
        (tmp_path / f"f{i}.md").write_text("x", encoding="utf-8")
    assert len(list_project_files(tmp_path, max_files=5)) == 5


def test_missing_root_is_empty_not_an_error(tmp_path: Path) -> None:
    assert list_project_files(tmp_path / "nope") == []


def test_is_openable_covers_markdown_and_text() -> None:
    assert is_openable("a.md") and is_openable("a.MD") and is_openable("a.txt")
    assert not is_openable("a.png") and not is_openable("a")

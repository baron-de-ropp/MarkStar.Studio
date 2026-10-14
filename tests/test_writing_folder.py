"""Writing-folder detection for the splash "This folder" row."""

from __future__ import annotations

from pathlib import Path

from markstar.domain.filewalk import is_writing_folder


def test_home_is_never_a_writing_folder(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / "readme.md").write_text("x", encoding="utf-8")
    assert is_writing_folder(tmp_path) is False


def test_root_is_never_a_writing_folder() -> None:
    assert is_writing_folder(Path("/")) is False


def test_folder_with_top_level_markdown_qualifies(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    (tmp_path / "home").mkdir()
    project = tmp_path / "manuscript"
    project.mkdir()
    (project / "ch1.md").write_text("x", encoding="utf-8")
    assert is_writing_folder(project) is True


def test_markdown_extension_variants_count(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    (tmp_path / "home").mkdir()
    project = tmp_path / "book"
    project.mkdir()
    (project / "notes.markdown").write_text("x", encoding="utf-8")
    assert is_writing_folder(project) is True


def test_nested_markdown_alone_does_not_qualify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    (tmp_path / "home").mkdir()
    project = tmp_path / "nested-only"
    project.mkdir()
    (project / "chapters").mkdir()
    (project / "chapters" / "one.md").write_text("x", encoding="utf-8")
    assert is_writing_folder(project) is False


def test_empty_folder_does_not_qualify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    (tmp_path / "home").mkdir()
    project = tmp_path / "empty"
    project.mkdir()
    assert is_writing_folder(project) is False


def test_nonexistent_path_does_not_qualify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    (tmp_path / "home").mkdir()
    assert is_writing_folder(tmp_path / "nope") is False

"""Tests for save path normalization."""

from __future__ import annotations

from pathlib import Path

from prose.app import ProseApp


def test_normalize_save_path_adds_md(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    p = ProseApp._normalize_save_path("chapter")
    assert p is not None
    assert p.name == "chapter.md"
    assert p.parent == tmp_path.resolve() or p.parent == tmp_path


def test_normalize_save_path_expanduser(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    p = ProseApp._normalize_save_path("~/notes/x.md")
    assert p is not None
    assert p == tmp_path / "notes" / "x.md"


def test_normalize_empty() -> None:
    assert ProseApp._normalize_save_path("   ") is None

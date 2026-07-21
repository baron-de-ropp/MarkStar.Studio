"""Save-path normalization: the pure resolver, and the base folder the app picks."""

from __future__ import annotations

import asyncio
from pathlib import Path

from markstar.app import MarkStarApp
from markstar.domain.savepath import resolve_save_path


def _run(coro):
    return asyncio.run(coro)


def test_bare_name_gets_md_suffix(tmp_path: Path) -> None:
    p = resolve_save_path("chapter", tmp_path)
    assert p == tmp_path / "chapter.md"


def test_existing_suffix_is_left_alone(tmp_path: Path) -> None:
    assert resolve_save_path("notes.txt", tmp_path) == tmp_path / "notes.txt"


def test_expanduser(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert resolve_save_path("~/notes/x.md", Path("/nowhere")) == (
        tmp_path / "notes" / "x.md"
    )


def test_absolute_path_ignores_base(tmp_path: Path) -> None:
    assert resolve_save_path("/etc/x.md", tmp_path) == Path("/etc/x.md")


def test_quotes_are_stripped(tmp_path: Path) -> None:
    assert resolve_save_path('"draft.md"', tmp_path) == tmp_path / "draft.md"


def test_empty_is_none(tmp_path: Path) -> None:
    assert resolve_save_path("   ", tmp_path) is None


def test_suffix_defaulting_can_be_disabled(tmp_path: Path) -> None:
    # Opening: a file with no extension is a legitimate thing to name.
    assert resolve_save_path("README", tmp_path, "") == tmp_path / "README"


def test_base_dir_prefers_project_root(tmp_path: Path) -> None:
    """A typed relative path lands in the project, not the launch directory."""

    async def go():
        app = MarkStarApp(path=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            return app._save_base_dir(), app._normalize_save_path("ch1")

    base, resolved = _run(go())
    assert base == tmp_path
    assert resolved == tmp_path / "ch1.md"


def test_base_dir_falls_back_to_active_file_folder(tmp_path: Path) -> None:
    """No project open → relative paths sit beside the file being edited."""
    sub = tmp_path / "book"
    sub.mkdir()
    target = sub / "chapter.md"
    target.write_text("# One", encoding="utf-8")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app._path_arg = None  # no project root
            app.workspace.open_path(target)
            return app._save_base_dir(), app._untitled_default()

    base, untitled = _run(go())
    assert base == sub
    assert untitled == sub / "untitled.md"

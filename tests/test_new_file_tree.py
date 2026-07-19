"""Folder-aware New File: target resolution + context-sensitive Ctrl+N flow."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from markstar.app import MarkStarApp
from markstar.ui.project_panel import ProjectPanel, WriterTree


def _run(coro):
    return asyncio.run(coro)


def _fake_tree(path) -> SimpleNamespace:
    node = SimpleNamespace(data=SimpleNamespace(path=path)) if path is not None else None
    return SimpleNamespace(cursor_node=node)


# --- target_dir resolution (pure, via a stubbed tree) ----------------------


def test_target_dir_folder_cursor_returns_folder(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    panel = ProjectPanel(tmp_path)
    panel.query_one = lambda *a, **k: _fake_tree(sub)  # type: ignore[assignment]
    assert panel.target_dir() == sub


def test_target_dir_file_cursor_returns_parent(tmp_path: Path) -> None:
    f = tmp_path / "sub" / "a.md"
    f.parent.mkdir()
    f.write_text("hi")
    panel = ProjectPanel(tmp_path)
    panel.query_one = lambda *a, **k: _fake_tree(f)  # type: ignore[assignment]
    assert panel.target_dir() == f.parent


def test_target_dir_no_cursor_returns_root(tmp_path: Path) -> None:
    panel = ProjectPanel(tmp_path)
    panel.query_one = lambda *a, **k: _fake_tree(None)  # type: ignore[assignment]
    assert panel.target_dir() == tmp_path


# --- context-sensitive Ctrl+N flow -----------------------------------------


def test_ctrl_n_in_tree_creates_and_opens(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "chapter"  # bare name → .md via _normalize_save_path

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.cmd_toggle_project_panel()
            await pilot.pause()
            app.query_one(WriterTree).focus()
            await pilot.pause()
            with patch.object(
                app, "push_screen_wait", AsyncMock(return_value=str(target))
            ):
                app.cmd_new_file()
                await pilot.pause()
                await pilot.pause()
            return app.document.path

    active = _run(go())
    created = tmp_path / "chapter.md"
    assert created.exists()  # empty file written to disk
    assert created.read_text() == ""
    assert Path(active) == created  # opened as the active document


def test_ctrl_n_never_overwrites_existing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "keep.md"
    existing.write_text("PRECIOUS")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.cmd_toggle_project_panel()
            await pilot.pause()
            app.query_one(WriterTree).focus()
            await pilot.pause()
            with patch.object(
                app, "push_screen_wait", AsyncMock(return_value=str(existing))
            ):
                app.cmd_new_file()
                await pilot.pause()
                await pilot.pause()
            return app.document.path

    active = _run(go())
    assert existing.read_text() == "PRECIOUS"  # untouched
    assert Path(active) == existing  # opened the existing file


def test_ctrl_n_without_tree_focus_makes_blank_buffer(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            # Editor focused, not the tree → legacy blank-buffer behavior.
            app.query_one("#editor").focus()
            await pilot.pause()
            called = {"prompted": False}

            async def _fake_prompt(*a, **k):
                called["prompted"] = True
                return None

            with patch.object(app, "push_screen_wait", _fake_prompt):
                app.cmd_new_file()
                await pilot.pause()
            return called["prompted"], app.document.path

    prompted, path = _run(go())
    assert prompted is False  # no name prompt off the tree
    assert path is None  # untitled in-memory buffer

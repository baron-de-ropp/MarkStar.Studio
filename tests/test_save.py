"""Saving: write-through to disk, dirty tracking, and sidecar cleanup."""

from __future__ import annotations

import asyncio

from markstar.app import MarkStarApp
from markstar.domain.autosave import sidecar_path


def _run(coro):
    return asyncio.run(coro)


def test_save_writes_file_and_clears_dirty(tmp_path) -> None:
    target = tmp_path / "note.md"

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.workspace.active.path = target
            ed = app.query_one("#editor")
            ed.load_text("# Hello\n\nbody")
            await pilot.pause()
            app._sync_document_from_editor()
            assert app.document.dirty  # editing marked it dirty
            app.cmd_save()
            await pilot.pause()
            return target.read_text(), app.document.dirty

    contents, dirty = _run(go())
    assert contents == "# Hello\n\nbody"
    assert dirty is False  # save clears the dirty flag


def test_save_removes_stale_autosave_sidecar(tmp_path) -> None:
    target = tmp_path / "note.md"
    side = sidecar_path(target)
    side.write_text("older autosave content")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.workspace.active.path = target
            app.query_one("#editor").load_text("fresh saved content")
            await pilot.pause()
            app.cmd_save()
            await pilot.pause()
            return side.exists()

    assert _run(go()) is False  # explicit save deletes the now-stale sidecar


def test_reopening_saved_file_round_trips(tmp_path) -> None:
    target = tmp_path / "round.md"

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.workspace.active.path = target
            app.query_one("#editor").load_text("line one\nline two")
            await pilot.pause()
            app.cmd_save()
            await pilot.pause()
            # Reopen in a fresh workspace tab and compare.
            app.workspace.open_path(target)
            app._load_active_into_editor()
            await pilot.pause()
            return app.document.text

    assert _run(go()) == "line one\nline two"

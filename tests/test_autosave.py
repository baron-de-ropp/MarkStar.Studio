"""Autosave sidecars: paths, write-while-dirty, delete-on-save, restore/discard."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

from markstar.app import MarkStarApp, MarkStarTextArea
from markstar.domain.autosave import sidecar_is_newer, sidecar_path


def _run(coro):
    return asyncio.run(coro)


def test_sidecar_path_and_newer(tmp_path) -> None:
    f = tmp_path / "chapter-01.md"
    f.write_text("x")
    assert sidecar_path(f) == tmp_path / ".chapter-01.md.autosave"
    assert sidecar_is_newer(f) is False
    sc = sidecar_path(f)
    sc.write_text("y")
    os.utime(sc, None)
    assert sidecar_is_newer(f) is True


def test_dirty_writes_sidecar_save_deletes_it(tmp_path) -> None:
    f = tmp_path / "c.md"
    f.write_text("original\n")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.workspace.open_path(f)
            app._load_active_into_editor()
            ed = app.query_one("#editor", MarkStarTextArea)
            ed.load_text("edited\n")
            app.document.set_text("edited\n")
            await pilot.pause()
            app._write_sidecar()
            sc = sidecar_path(f)
            wrote = sc.exists() and "edited" in sc.read_text()
            real_untouched = f.read_text() == "original\n"
            app._write_active_document()
            saved = "edited" in f.read_text()
            deleted = not sc.exists()
            return wrote, real_untouched, saved, deleted

    wrote, untouched, saved, deleted = _run(go())
    assert wrote and untouched and saved and deleted


def test_restore_loads_sidecar(tmp_path) -> None:
    f = tmp_path / "c.md"
    f.write_text("saved version\n")
    sc = sidecar_path(f)
    sc.write_text("RECOVERED\n")
    os.utime(sc, None)

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            with patch.object(
                app, "push_screen_wait", AsyncMock(return_value="restore")
            ):
                app.workspace.open_path(f)
                app._load_active_into_editor()
                await app._maybe_restore(f)
                await pilot.pause()
            return app.document.text

    assert "RECOVERED" in _run(go())


def test_discard_removes_sidecar(tmp_path) -> None:
    f = tmp_path / "c.md"
    f.write_text("saved\n")
    sc = sidecar_path(f)
    sc.write_text("junk\n")
    os.utime(sc, None)

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            with patch.object(
                app, "push_screen_wait", AsyncMock(return_value="discard")
            ):
                app.workspace.open_path(f)
                app._load_active_into_editor()
                await app._maybe_restore(f)
                await pilot.pause()
            return sc.exists(), app.document.text

    exists, text = _run(go())
    assert exists is False
    assert text == "saved\n"


def test_autosave_off_writes_nothing(tmp_path) -> None:
    f = tmp_path / "c.md"
    f.write_text("original\n")

    async def go():
        app = MarkStarApp()
        app.prefs.autosave = False
        async with app.run_test() as pilot:
            app.workspace.open_path(f)
            app._load_active_into_editor()
            app.document.set_text("edited\n")
            await pilot.pause()
            app._write_sidecar()
            return sidecar_path(f).exists()

    assert _run(go()) is False

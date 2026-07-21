"""Works-style close guard: Save / Don't Save / Cancel on close, close-all, quit."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from markstar.app import MarkStarApp
from markstar.domain.autosave import sidecar_path


def _run(coro):
    return asyncio.run(coro)


def _seed_dirty_tabs(app) -> None:
    a = app.workspace.active
    a.set_text("first — dirty")
    b = app.workspace.new_document(text="second — dirty")
    b.set_text("second — edited")
    # active back to the first tab
    app.workspace.set_active(0)


async def _settle(pilot, times: int = 6) -> None:
    for _ in range(times):
        await pilot.pause()


# ---- single-tab close -------------------------------------------------------


def test_close_dirty_cancel_keeps_the_tab(tmp_path) -> None:
    target = tmp_path / "keep.md"
    target.write_text("original", encoding="utf-8")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.workspace.open_path(target)
            app.workspace.active.set_text("edited, not saved")
            app._load_active_into_editor()
            await pilot.pause()
            with patch.object(
                app, "push_screen_wait", AsyncMock(return_value="cancel")
            ):
                app.cmd_close()
                await _settle(pilot)
            return app.workspace.count, target.read_text(encoding="utf-8")

    count, on_disk = _run(go())
    assert count == 1
    assert on_disk == "original"  # cancelled → nothing written, nothing lost


def test_close_dirty_save_writes_then_closes(tmp_path) -> None:
    target = tmp_path / "ch.md"
    target.write_text("original", encoding="utf-8")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.workspace.open_path(target)
            app.workspace.new_document(text="another tab")
            app.workspace.set_active(0)
            app.workspace.active.set_text("saved edit")
            app._load_active_into_editor()
            await pilot.pause()
            with patch.object(
                app, "push_screen_wait", AsyncMock(return_value="save")
            ):
                app.cmd_close()
                await _settle(pilot)
            return app.workspace.count, target.read_text(encoding="utf-8")

    count, on_disk = _run(go())
    assert count == 1  # the saved tab closed, the other remains
    assert on_disk == "saved edit"


def test_close_dirty_discard_drops_the_autosave_sidecar(tmp_path) -> None:
    """Don't Save must not leave a sidecar that resurrects the work on reopen."""
    target = tmp_path / "ch.md"
    target.write_text("original", encoding="utf-8")
    side = sidecar_path(target)
    side.write_text("half-written thought", encoding="utf-8")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.workspace.open_path(target)
            app.workspace.active.set_text("edited")
            app._load_active_into_editor()
            await pilot.pause()
            with patch.object(
                app, "push_screen_wait", AsyncMock(return_value="discard")
            ):
                app.cmd_close()
                await _settle(pilot)
            return side.exists(), target.read_text(encoding="utf-8")

    sidecar_left, on_disk = _run(go())
    assert sidecar_left is False
    assert on_disk == "original"  # discarded, so the file is untouched


def test_close_untitled_save_cancelled_at_prompt_keeps_tab() -> None:
    """Save → the path prompt → Esc. Cancelling the name cancels the close."""

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.workspace.active.set_text("unnamed work")
            app._load_active_into_editor()
            await pilot.pause()
            # dialog says "save", then the PathPrompt returns None (Esc)
            with patch.object(
                app, "push_screen_wait", AsyncMock(side_effect=["save", None])
            ):
                app.cmd_close()
                await _settle(pilot)
            return app.workspace.count, app.document.text

    count, text = _run(go())
    assert count == 1
    assert text == "unnamed work"  # still there, still unsaved


def test_close_clean_tab_asks_nothing() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.workspace.new_document(text="clean")
            app._load_active_into_editor()  # editor must hold this tab's text
            await pilot.pause()
            app.workspace.active.mark_saved()
            asked = AsyncMock(return_value="cancel")
            with patch.object(app, "push_screen_wait", asked):
                app.cmd_close()
                await _settle(pilot)
            return asked.await_count, app.workspace.count

    awaited, count = _run(go())
    assert awaited == 0  # no dialog for a clean buffer
    assert count == 1


# ---- close others / close all ----------------------------------------------


def test_close_others_cancel_keeps_them() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            _seed_dirty_tabs(app)
            app._load_active_into_editor()
            await pilot.pause()
            with patch.object(
                app, "push_screen_wait", AsyncMock(return_value="cancel")
            ):
                app.cmd_close_others()
                await _settle(pilot)
            return app.workspace.count

    assert _run(go()) == 2


def test_close_others_discard_closes_them() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            _seed_dirty_tabs(app)
            app._load_active_into_editor()
            await pilot.pause()
            with patch.object(
                app, "push_screen_wait", AsyncMock(return_value="discard")
            ):
                app.cmd_close_others()
                await _settle(pilot)
            return app.workspace.count, app.document.text

    count, text = _run(go())
    assert count == 1
    assert text == "first — dirty"  # the kept tab is the one we were on


def test_close_all_discard_leaves_one_empty_tab() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            _seed_dirty_tabs(app)
            app._load_active_into_editor()
            await pilot.pause()
            with patch.object(
                app, "push_screen_wait", AsyncMock(return_value="discard")
            ):
                app.cmd_close_all()
                await _settle(pilot)
            return app.workspace.count, app.document.text

    count, text = _run(go())
    assert count == 1 and text == ""


# ---- quit -------------------------------------------------------------------


def test_quit_save_all_writes_every_titled_tab(tmp_path) -> None:
    one = tmp_path / "one.md"
    two = tmp_path / "two.md"
    one.write_text("old one", encoding="utf-8")
    two.write_text("old two", encoding="utf-8")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.workspace.open_path(one)
            app.workspace.active.set_text("new one")
            app.workspace.open_path(two)
            app.workspace.active.set_text("new two")
            app.workspace.set_active(0)
            app._load_active_into_editor()
            await pilot.pause()
            # First dialog answers "save_all"; the rest save without asking.
            with patch.object(
                app, "push_screen_wait", AsyncMock(return_value="save_all")
            ):
                with patch.object(app, "exit") as exited:
                    app.cmd_quit()
                    await _settle(pilot)
                    quit_called = exited.called
            return quit_called, one.read_text("utf-8"), two.read_text("utf-8")

    quit_called, first, second = _run(go())
    assert quit_called is True
    assert first == "new one"
    assert second == "new two"


def test_quit_cancel_midwalk_aborts_and_keeps_tabs() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            _seed_dirty_tabs(app)
            app._load_active_into_editor()
            await pilot.pause()
            with patch.object(
                app, "push_screen_wait", AsyncMock(side_effect=["discard", "cancel"])
            ):
                with patch.object(app, "exit") as exited:
                    app.cmd_quit()
                    await _settle(pilot)
                    quit_called = exited.called
            return quit_called, app.workspace.count

    quit_called, count = _run(go())
    assert quit_called is False  # cancel aborts the quit
    assert count == 2  # nothing was closed


def test_quit_with_no_dirty_tabs_exits_immediately() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            asked = AsyncMock(return_value="cancel")
            with patch.object(app, "push_screen_wait", asked):
                with patch.object(app, "exit") as exited:
                    app.cmd_quit()
                    await _settle(pilot)
                    return asked.await_count, exited.called

    awaited, exited = _run(go())
    assert awaited == 0
    assert exited is True

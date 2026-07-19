"""Unsaved-changes confirm flows for close-others / close-all (yes vs no)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from markstar.app import MarkStarApp


def _run(coro):
    return asyncio.run(coro)


def _seed_dirty_tabs(app) -> None:
    a = app.workspace.active
    a.set_text("first — dirty")
    b = app.workspace.new_document(text="second — dirty")
    b.set_text("second — edited")
    # active back to the first tab
    app.workspace.set_active(0)


def test_close_others_confirmed_discards_them(tmp_path) -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            _seed_dirty_tabs(app)
            app._load_active_into_editor()
            await pilot.pause()
            assert app.workspace.count == 2
            with patch.object(app, "push_screen_wait", AsyncMock(return_value=True)):
                app.cmd_close_others()
                for _ in range(4):
                    await pilot.pause()
            return app.workspace.count

    assert _run(go()) == 1  # confirmed → others closed


def test_close_others_declined_keeps_them() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            _seed_dirty_tabs(app)
            app._load_active_into_editor()
            await pilot.pause()
            with patch.object(app, "push_screen_wait", AsyncMock(return_value=False)):
                app.cmd_close_others()
                for _ in range(4):
                    await pilot.pause()
            return app.workspace.count

    assert _run(go()) == 2  # declined → nothing closed


def test_close_all_declined_keeps_tabs() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            _seed_dirty_tabs(app)
            app._load_active_into_editor()
            await pilot.pause()
            with patch.object(app, "push_screen_wait", AsyncMock(return_value=False)):
                app.cmd_close_all()
                for _ in range(4):
                    await pilot.pause()
            return app.workspace.count

    assert _run(go()) == 2  # declined → tabs preserved


def test_close_all_confirmed_leaves_one_empty_tab() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            _seed_dirty_tabs(app)
            app._load_active_into_editor()
            await pilot.pause()
            with patch.object(app, "push_screen_wait", AsyncMock(return_value=True)):
                app.cmd_close_all()
                for _ in range(4):
                    await pilot.pause()
            return app.workspace.count, app.document.text

    count, text = _run(go())
    assert count == 1 and text == ""  # collapsed to a single empty buffer

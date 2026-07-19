"""Find/replace bar — key commands (Ctrl+L replace all, Enter replace one)."""

from __future__ import annotations

import asyncio

from prose.app import ProseApp
from prose.ui.find_bar import FindBar


def _run(coro):
    return asyncio.run(coro)


def test_ctrl_l_replaces_all() -> None:
    async def go():
        app = ProseApp()
        async with app.run_test() as pilot:
            app.query_one("#editor").load_text("aa bb aa")
            app.document.set_text("aa bb aa")
            app.registry.execute("replace")
            await pilot.pause()
            bar = app.query_one("#find-bar", FindBar)
            bar.query_one("#find-input").value = "aa"
            bar.query_one("#replace-input").value = "Q"
            bar.query_one("#replace-input").focus()
            await pilot.pause()
            await pilot.press("ctrl+l")
            await pilot.pause()
            return app.document.text

    assert _run(go()) == "Q bb Q"


def test_ctrl_l_does_not_leak_to_editor_select_all() -> None:
    """Ctrl+L in the replace field must not touch the editor selection."""

    async def go():
        app = ProseApp()
        async with app.run_test() as pilot:
            app.query_one("#editor").load_text("aa bb aa")
            app.document.set_text("aa bb aa")
            app.registry.execute("replace")
            await pilot.pause()
            bar = app.query_one("#find-bar", FindBar)
            bar.query_one("#find-input").value = "aa"
            bar.query_one("#replace-input").value = "Q"
            bar.query_one("#replace-input").focus()
            await pilot.pause()
            await pilot.press("ctrl+l")
            await pilot.pause()
            return app.document.text

    assert _run(go()) == "Q bb Q"


def test_enter_in_replace_field_replaces_one() -> None:
    async def go():
        app = ProseApp()
        async with app.run_test() as pilot:
            app.query_one("#editor").load_text("aa bb aa")
            app.document.set_text("aa bb aa")
            app.registry.execute("replace")
            await pilot.pause()
            bar = app.query_one("#find-bar", FindBar)
            bar.query_one("#find-input").value = "aa"
            bar.query_one("#replace-input").value = "Q"
            bar.query_one("#replace-input").focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            return app.document.text

    assert _run(go()).count("Q") == 1

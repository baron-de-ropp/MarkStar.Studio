"""F7 spellcheck toggle: keybinding, live checked-state, and menu ✓ marker."""

from __future__ import annotations

import asyncio

from textual.widgets import OptionList

from markstar.app import MarkStarApp
from markstar.ui.menu_bar import MenuBar


def _run(coro):
    return asyncio.run(coro)


def test_spellcheck_command_bound_to_f7() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test():
            cmd = app.registry.get("toggle_spellcheck")
            return cmd.binding

    assert _run(go()) == "f7"


def test_spellcheck_checked_reflects_state_and_toggles() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            cmd = app.registry.get("toggle_spellcheck")
            before = cmd.is_checked()
            app.cmd_toggle_spellcheck()
            await pilot.pause()
            after = cmd.is_checked()
            return before, after, app._spell.enabled

    before, after, live = _run(go())
    assert before is True  # default prefs.spellcheck is True
    assert after is False
    assert after == live  # checker mirrors the controller's real state


def test_tools_menu_shows_check_marker() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            menu = app.query_one("#app-menu", MenuBar)
            menu.open_menu("Tools")
            await pilot.pause()
            options = app.query_one("#menu-options", OptionList)
            labels = [
                str(options.get_option_at_index(i).prompt)
                for i in range(options.option_count)
            ]
            # Toggle off, reopen, and capture again.
            menu.close_menu()
            app.cmd_toggle_spellcheck()
            await pilot.pause()
            menu.open_menu("Tools")
            await pilot.pause()
            options = app.query_one("#menu-options", OptionList)
            labels_off = [
                str(options.get_option_at_index(i).prompt)
                for i in range(options.option_count)
            ]
            return labels, labels_off

    on_labels, off_labels = _run(go())
    on_row = next(r for r in on_labels if "Spellcheck" in r)
    off_row = next(r for r in off_labels if "Spellcheck" in r)
    assert "✓" in on_row  # checked when spellcheck is on
    assert "✓" not in off_row  # marker clears when off
    assert "F7" in on_row  # shortcut shown, function key uppercased

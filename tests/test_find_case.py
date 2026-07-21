"""Case-sensitive find: the toggle actually changes what matches."""

from __future__ import annotations

import asyncio

from markstar.app import MarkStarApp
from markstar.ui.find_bar import FindBar


def _run(coro):
    return asyncio.run(coro)


TEXT = "The Warden sleeps. the warden wakes. WARDEN."


async def _prepare(pilot, app, query: str):
    app.workspace.active.set_text(TEXT)
    app._load_active_into_editor()
    await pilot.pause()
    app.cmd_find()
    await pilot.pause()
    bar = app.query_one("#find-bar", FindBar)
    bar.query_one("#find-input").value = query
    await pilot.pause()
    return bar


def test_default_is_case_insensitive() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await _prepare(pilot, app, "warden")
            return app._find.case_sensitive, len(
                app.query_one("#editor")._search_by_line.get(0, [])
            )

    case, hits = _run(go())
    assert case is False
    assert hits == 3  # Warden, warden, WARDEN


def test_toggling_narrows_to_exact_case() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await _prepare(pilot, app, "warden")
            app._find.toggle_case_sensitive()
            await pilot.pause()
            return app._find.case_sensitive, len(
                app.query_one("#editor")._search_by_line.get(0, [])
            )

    case, hits = _run(go())
    assert case is True
    assert hits == 1  # only the lowercase "warden"


def test_toggle_is_reversible() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await _prepare(pilot, app, "warden")
            app._find.toggle_case_sensitive()
            app._find.toggle_case_sensitive()
            await pilot.pause()
            return len(app.query_one("#editor")._search_by_line.get(0, []))

    assert _run(go()) == 3


def test_hint_strip_reports_the_mode() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            bar = await _prepare(pilot, app, "warden")
            from textual.widgets import Static

            before = bar.query_one("#find-hints", Static).content
            bar.set_case_sensitive(True)
            await pilot.pause()
            after = bar.query_one("#find-hints", Static).content
            return str(before), str(after)

    before, after = _run(go())
    assert "any case" in before
    assert "match case" in after


def test_replace_all_respects_case_mode() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            bar = await _prepare(pilot, app, "warden")
            bar.expand_replace()
            await pilot.pause()
            bar.query_one("#replace-input").value = "keeper"
            app._find.toggle_case_sensitive()   # exact case only
            await pilot.pause()
            app._find.replace_all()
            await pilot.pause()
            return app.document.text

    text = _run(go())
    assert "the keeper wakes" in text     # replaced
    assert "The Warden sleeps" in text    # left alone
    assert "WARDEN." in text              # left alone

"""Replace-all driven end-to-end through the app + find bar (not just the widget)."""

from __future__ import annotations

import asyncio

from markstar.app import MarkStarApp
from markstar.ui.find_bar import FindBar, FindInput


def _run(coro):
    return asyncio.run(coro)


def test_replace_all_rewrites_every_match_and_syncs_editor() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor")
            ed.load_text("cat sat on a cat mat, cat")
            await pilot.pause()
            app.cmd_replace()  # open the bar in replace mode
            await pilot.pause()
            bar = app.query_one("#find-bar", FindBar)
            bar.query_one("#find-input", FindInput).value = "cat"
            bar.query_one("#replace-input", FindInput).value = "dog"
            await pilot.pause()
            app.cmd_replace_all()
            await pilot.pause()
            return app.document.text, ed.text

    doc_text, editor_text = _run(go())
    assert doc_text == "dog sat on a dog mat, dog"
    assert editor_text == doc_text  # editor was pushed back in sync


def test_replace_all_empty_replacement_deletes_matches() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.query_one("#editor").load_text("a-b-c-d")
            await pilot.pause()
            app.cmd_replace()
            await pilot.pause()
            bar = app.query_one("#find-bar", FindBar)
            bar.query_one("#find-input", FindInput).value = "-"
            bar.query_one("#replace-input", FindInput).value = ""
            await pilot.pause()
            app.cmd_replace_all()
            await pilot.pause()
            return app.document.text

    assert _run(go()) == "abcd"

"""Line move/duplicate actions — scoped editor edits with granular undo."""

from __future__ import annotations

import asyncio

from markstar.app import MarkStarApp


def _run(coro):
    return asyncio.run(coro)


def test_move_line_up_swaps_with_line_above() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor")
            ed.load_text("one\ntwo\nthree")
            ed.move_cursor((2, 0))  # on "three"
            app.action_move_line_up()
            await pilot.pause()
            return ed.text, ed.cursor_location

    text, cursor = _run(go())
    assert text == "one\nthree\ntwo"
    assert cursor == (1, 0)  # caret follows the moved line


def test_move_line_up_noop_on_first_line() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor")
            ed.load_text("a\nb")
            ed.move_cursor((0, 0))
            app.action_move_line_up()
            await pilot.pause()
            return ed.text

    assert _run(go()) == "a\nb"


def test_move_line_down_swaps_with_line_below() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor")
            ed.load_text("one\ntwo\nthree")
            ed.move_cursor((0, 0))
            app.action_move_line_down()
            await pilot.pause()
            return ed.text

    assert _run(go()) == "two\none\nthree"


def test_move_line_down_noop_on_last_line() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor")
            ed.load_text("a\nb")
            ed.move_cursor((1, 0))
            app.action_move_line_down()
            await pilot.pause()
            return ed.text

    assert _run(go()) == "a\nb"


def test_duplicate_line_and_granular_undo() -> None:
    """Duplicate copies the caret's line below; undo removes just that copy
    (was a whole-document replace before — undo reverted everything)."""

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor")
            ed.load_text("one\ntwo")
            ed.move_cursor((1, 1))
            app.action_duplicate_line()
            await pilot.pause()
            after_dup = ed.text
            ed.undo()
            await pilot.pause()
            return after_dup, ed.text

    after_dup, after_undo = _run(go())
    assert after_dup == "one\ntwo\ntwo"
    assert after_undo == "one\ntwo"  # granular: only the duplicate is undone

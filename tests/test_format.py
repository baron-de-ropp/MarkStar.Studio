"""Format-menu Markdown insertion, exercised through the real app + editor."""

from __future__ import annotations

import asyncio

from textual.widgets.text_area import Selection

from markstar.app import MarkStarApp


def _run(coro):
    return asyncio.run(coro)


async def _wrap_case(command: str, text: str, sel: Selection, expected: str) -> str:
    app = MarkStarApp()
    async with app.run_test() as pilot:
        editor = app.query_one("#editor")
        editor.load_text(text)
        editor.selection = sel
        getattr(app, command)()
        await pilot.pause()
        return editor.text


def test_bold_wraps_selection() -> None:
    out = _run(_wrap_case("cmd_bold", "hello world", Selection((0, 0), (0, 5)), None))
    assert out == "**hello** world"


def test_italic_wraps_selection() -> None:
    out = _run(_wrap_case("cmd_italic", "hi there", Selection((0, 0), (0, 2)), None))
    assert out == "*hi* there"


def test_strikethrough_wraps_selection() -> None:
    out = _run(_wrap_case("cmd_strikethrough", "nope", Selection((0, 0), (0, 4)), None))
    assert out == "~~nope~~"


def test_heading_prefixes_line() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            editor = app.query_one("#editor")
            editor.load_text("Title")
            editor.move_cursor((0, 0))
            app.cmd_heading()
            await pilot.pause()
            return editor.text

    assert _run(go()) == "# Title"


def test_bold_toggles_word_under_caret() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor")
            ed.load_text("the quick fox")
            ed.move_cursor((0, 7))  # inside "quick", no selection
            await pilot.pause()
            app.cmd_bold()
            await pilot.pause()
            after_bold = ed.text
            ed.move_cursor((0, 8))  # inside **quick**
            app.cmd_bold()
            await pilot.pause()
            return after_bold, ed.text

    bolded, unbolded = _run(go())
    assert bolded == "the **quick** fox"
    assert unbolded == "the quick fox"


def test_italic_toggles_selection() -> None:
    from textual.widgets.text_area import Selection

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor")
            ed.load_text("hello world")
            ed.selection = Selection((0, 0), (0, 5))
            await pilot.pause()
            app.cmd_italic()
            await pilot.pause()
            on = ed.text
            ed.selection = Selection((0, 1), (0, 6))  # "hello" inside *…*
            app.cmd_italic()
            await pilot.pause()
            return on, ed.text

    on, off = _run(go())
    assert on == "*hello* world"
    assert off == "hello world"


def test_bold_with_no_selection_inserts_markers() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            editor = app.query_one("#editor")
            editor.load_text("")
            editor.move_cursor((0, 0))
            app.cmd_bold()
            await pilot.pause()
            return editor.text

    assert _run(go()) == "****"

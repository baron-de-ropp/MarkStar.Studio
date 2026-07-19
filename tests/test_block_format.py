"""Block-level Format commands: line prefixes, rule, and code fence."""

from __future__ import annotations

import asyncio

from textual.widgets.text_area import Selection

from markstar.app import MarkStarApp


def _run(coro):
    return asyncio.run(coro)


async def _apply(command: str, text: str, *, row: int = 0, col: int = 0) -> str:
    app = MarkStarApp()
    async with app.run_test() as pilot:
        ed = app.query_one("#editor")
        ed.load_text(text)
        ed.move_cursor((row, col))
        await pilot.pause()
        getattr(app, command)()
        await pilot.pause()
        return ed.text


def test_heading_prefixes_current_line() -> None:
    assert _run(_apply("cmd_heading", "Title")) == "# Title"


def test_blockquote_prefixes_current_line() -> None:
    assert _run(_apply("cmd_blockquote", "quote me")) == "> quote me"


def test_bullet_list_prefix() -> None:
    assert _run(_apply("cmd_bullet_list", "item")) == "- item"


def test_numbered_list_prefix() -> None:
    assert _run(_apply("cmd_numbered_list", "item")) == "1. item"


def test_heading_only_affects_caret_line() -> None:
    out = _run(_apply("cmd_heading", "one\ntwo\nthree", row=1))
    assert out == "one\n# two\nthree"


def test_hrule_inserts_divider() -> None:
    assert "---" in _run(_apply("cmd_hrule", "above"))


def test_code_fence_wraps_selection() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor")
            ed.load_text("print(1)")
            ed.selection = Selection((0, 0), (0, 8))
            await pilot.pause()
            app.cmd_code_fence()
            await pilot.pause()
            return ed.text

    assert _run(go()) == "```\nprint(1)\n```"

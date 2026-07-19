"""Mouse pointer shape: typewriter caret over text, hand over links."""

from __future__ import annotations

import asyncio

from markstar.app import MarkStarApp, MarkStarTextArea


def _run(coro):
    return asyncio.run(coro)


def test_editor_and_inputs_use_text_caret() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor", MarkStarTextArea)
            app.registry.execute("find")
            await pilot.pause()
            fi = app.query_one("#find-input")
            return str(ed.styles.pointer), str(fi.styles.pointer)

    ed_ptr, input_ptr = _run(go())
    assert ed_ptr == "text"
    assert input_ptr == "text"


def test_link_hover_detection() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor", MarkStarTextArea)
            ed.load_text("see [my link](https://x.com) here")
            await pilot.pause()
            ed.get_target_document_location = lambda ev: (0, 10)  # inside the link
            over = ed._location_over_link(None)
            ed.get_target_document_location = lambda ev: (0, 1)   # plain text
            not_over = ed._location_over_link(None)
            return over, not_over

    over, not_over = _run(go())
    assert over is True
    assert not_over is False

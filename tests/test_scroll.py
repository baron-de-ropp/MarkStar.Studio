"""Scroll-past-end: the last line can rest ~1/3 down the screen (2/3 empty)."""

from __future__ import annotations

import asyncio

from markstar.app import MarkStarApp


def _run(coro):
    return asyncio.run(coro)


def _long_doc(n: int = 60) -> str:
    return "\n".join(f"line {i}" for i in range(n))


def test_overflowing_doc_gains_bottom_room() -> None:
    """A document taller than the viewport gets ~2/3-of-a-screen of virtual room
    below it, so the last line can be scrolled up to ~1/3 height."""

    async def go():
        app = MarkStarApp()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            ed = app.query_one("#editor")
            ed.load_text(_long_doc(60))
            await pilot.pause()
            await pilot.pause()
            return ed.size.height, ed.wrapped_document.height, ed.virtual_size.height

    view, content, virtual = _run(go())
    assert content == 60
    assert virtual == content + int(view * (2 / 3))
    # At max scroll the last line sits ~1/3 down, not pinned to the bottom.
    assert (virtual - view) < (content - 1)


def test_short_doc_gets_no_phantom_scroll() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            ed = app.query_one("#editor")
            ed.load_text("a\nb\nc")
            await pilot.pause()
            return ed.virtual_size.height

    assert _run(go()) == 3  # no extra room when the doc fits


def test_padding_is_idempotent_not_compounding() -> None:
    """Re-running the size refresh must not keep stacking bottom room."""

    async def go():
        app = MarkStarApp()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            ed = app.query_one("#editor")
            ed.load_text(_long_doc(60))
            await pilot.pause()
            first = ed.virtual_size.height
            for _ in range(5):
                ed._refresh_size()
            return first, ed.virtual_size.height

    first, after = _run(go())
    assert first == after


def test_disabling_removes_the_room() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            ed = app.query_one("#editor")
            ed.load_text(_long_doc(60))
            await pilot.pause()
            ed.scroll_past_end = False
            ed._refresh_size()
            return ed.virtual_size.height

    assert _run(go()) == 60  # back to exact content height


def test_room_recomputes_on_resize() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            ed = app.query_one("#editor")
            ed.load_text(_long_doc(60))
            await pilot.pause()
            small = (ed.size.height, ed.virtual_size.height)
            await pilot.resize_terminal(80, 40)
            for _ in range(4):
                await pilot.pause()
            big = (ed.size.height, ed.virtual_size.height)
            return small, big

    small, big = _run(go())
    assert small[1] == 60 + int(small[0] * (2 / 3))
    assert big[1] == 60 + int(big[0] * (2 / 3))
    assert big[1] > small[1]  # taller viewport → more room

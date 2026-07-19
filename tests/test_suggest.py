"""Suggestion popup: replaces the word under the caret; no-op on correct words."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from markstar.app import MarkStarApp, MarkStarTextArea


def _run(coro):
    return asyncio.run(coro)


def test_suggestion_replaces_word_under_caret() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test(size=(90, 16)) as pilot:
            app._speller.prime()
            ed = app.query_one("#editor", MarkStarTextArea)
            ed.load_text("The quikc brown fox")
            app.document.set_text("The quikc brown fox")
            ed.move_cursor((0, 7))
            await pilot.pause()
            with patch.object(
                app, "push_screen_wait", AsyncMock(return_value="quick")
            ):
                await app._suggest_async(
                    0, 4, 9, "quikc", app._speller.suggestions("quikc"),
                    ed.cursor_screen_offset,
                )
                await pilot.pause()
            return ed.text

    assert _run(go()) == "The quick brown fox"


def test_correct_word_gives_no_popup() -> None:
    async def go():
        app = MarkStarApp()
        toasts: list = []
        async with app.run_test() as pilot:
            app._speller.prime()
            ed = app.query_one("#editor", MarkStarTextArea)
            ed.load_text("The brown fox")
            app.document.set_text("The brown fox")
            ed.move_cursor((0, 1))  # in "The"
            app.notify = lambda *a, **k: toasts.append(a)
            with patch.object(app, "push_screen_wait", AsyncMock()) as pw:
                app.cmd_suggest()
                await pilot.pause()
                return pw.called, toasts

    called, toasts = _run(go())
    assert called is False  # no popup
    assert any("correctly" in str(t) for t in toasts)


def test_cancel_leaves_word_unchanged() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test(size=(90, 16)) as pilot:
            app._speller.prime()
            ed = app.query_one("#editor", MarkStarTextArea)
            ed.load_text("a quikc word")
            app.document.set_text("a quikc word")
            ed.move_cursor((0, 3))
            await pilot.pause()
            with patch.object(app, "push_screen_wait", AsyncMock(return_value="")):
                await app._suggest_async(
                    0, 2, 7, "quikc", ["quick"], ed.cursor_screen_offset
                )
                await pilot.pause()
            return ed.text

    assert _run(go()) == "a quikc word"

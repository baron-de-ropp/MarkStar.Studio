"""Typing must not get slower as a manuscript grows.

Textual's ``WrappedDocument.height`` sums over every wrapped line and is not
cached, and ``TextArea._render_line`` reads it once per rendered row — roughly
25 passes over the whole document per keystroke. ui/fast_height makes it O(1);
these tests hold that line and check the equivalence it relies on.

Note the road not taken: having ``_refresh_size`` reuse the height super() just
computed looks like an obvious saving, but assigning ``virtual_size`` re-enters
``_refresh_size``, so reading it back compounds the scroll-past-end padding.
tests/test_scroll.py catches that.
"""

from __future__ import annotations

import asyncio

from textual.widgets import TextArea

from markstar.app import MarkStarApp
from markstar.config import Preferences


def _run(coro):
    return asyncio.run(coro)


def test_scroll_past_end_still_extends_the_scrollable_area() -> None:
    """The optimisation must not cost the typewriter-room behaviour it serves."""

    async def go():
        prefs = Preferences()
        prefs.spellcheck = False
        app = MarkStarApp(prefs=prefs)
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            editor = app.query_one("#editor", TextArea)
            editor.text = "\n".join(f"line {i}" for i in range(500))
            for _ in range(6):
                await pilot.pause()
            # Refresh once more so the extra room and the viewport height that
            # produced it are from the same pass — the widget is resized several
            # times during layout, and comparing across two of them is racy.
            editor._refresh_size()
            return editor.virtual_size.height, editor.wrapped_document.height, editor.size.height

    virtual, content, view = _run(go())
    assert content > view                      # the document overflows the screen
    assert virtual > content                   # and there is room to scroll past it
    assert virtual - content <= view           # but not more than a screenful


def test_short_document_gains_no_phantom_scroll_room() -> None:
    async def go():
        prefs = Preferences()
        prefs.spellcheck = False
        app = MarkStarApp(prefs=prefs)
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            editor = app.query_one("#editor", TextArea)
            editor.text = "one\ntwo\nthree"
            for _ in range(6):
                await pilot.pause()
            return editor.virtual_size.height, editor.wrapped_document.height

    virtual, content = _run(go())
    assert virtual == content  # nothing added: the file fits on screen


# --- O(1) wrapped-document height -------------------------------------------


def test_height_is_o1_not_a_pass_over_the_document() -> None:
    """Textual's TextArea._render_line reads height once per rendered row.

    Left as a sum over every line, that is ~25 passes over the whole document
    per keystroke, and typing slows down as a manuscript grows.
    """
    from textual.document._wrapped_document import WrappedDocument

    async def go():
        prefs = Preferences()
        prefs.spellcheck = False
        app = MarkStarApp(prefs=prefs)
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            editor = app.query_one("#editor", TextArea)
            editor.text = "\n".join("word " * 30 for _ in range(800))
            for _ in range(6):
                await pilot.pause()
            wrapped = editor.wrapped_document
            # The O(1) route and the original definition must agree exactly.
            slow = sum(len(o) + 1 for o in wrapped._wrap_offsets)
            return wrapped.height, slow, len(wrapped._offset_to_line_info)

    height, slow, offsets = _run(go())
    assert height == slow == offsets


def test_height_matches_after_edits_and_rewrap() -> None:
    """The O(1) source of truth must survive insertions, deletions and re-wraps."""

    async def go():
        prefs = Preferences()
        prefs.spellcheck = False
        app = MarkStarApp(prefs=prefs)
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            editor = app.query_one("#editor", TextArea)
            editor.text = "\n".join("word " * 30 for _ in range(200))
            for _ in range(4):
                await pilot.pause()
            editor.move_cursor((5, 0))

            def agrees() -> bool:
                w = editor.wrapped_document
                return w.height == sum(len(o) + 1 for o in w._wrap_offsets)

            checks = [agrees()]
            for _ in range(10):
                await pilot.press("x")
            await pilot.pause()
            checks.append(agrees())
            await pilot.press("enter")
            await pilot.pause()
            checks.append(agrees())
            for _ in range(5):
                await pilot.press("backspace")
            await pilot.pause()
            checks.append(agrees())
            await pilot.resize_terminal(60, 32)
            for _ in range(6):
                await pilot.pause()
            checks.append(agrees())
            await pilot.resize_terminal(140, 32)
            for _ in range(6):
                await pilot.pause()
            checks.append(agrees())
            return checks

    assert all(_run(go()))


def test_install_is_idempotent() -> None:
    from markstar.ui.fast_height import install

    install()
    install()  # must not wrap itself twice
    from textual.document._wrapped_document import WrappedDocument

    assert isinstance(WrappedDocument.height, property)

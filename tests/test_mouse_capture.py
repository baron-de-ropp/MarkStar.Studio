"""Mouse Capture toggle — releases/reacquires terminal mouse tracking."""

from __future__ import annotations

import asyncio
import types

from textual.drivers.linux_driver import LinuxDriver

from markstar.app import MarkStarApp


def _run(coro):
    return asyncio.run(coro)


def test_toggle_mouse_capture_writes_tracking_sequences() -> None:
    """Grafts the real LinuxDriver methods (they only use write/flush/_mouse)
    onto the headless test driver so the exact terminal sequences are asserted.
    """

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            drv = app._driver
            writes: list[str] = []
            drv.write = lambda data: writes.append(data)
            drv.flush = lambda: None
            drv._enable_mouse_support = types.MethodType(
                LinuxDriver._enable_mouse_support, drv
            )
            drv._disable_mouse_support = types.MethodType(
                LinuxDriver._disable_mouse_support, drv
            )

            app.registry.execute("toggle_mouse")
            await pilot.pause()
            released = (
                drv._mouse is False
                and any("1000l" in w for w in writes)
                and any("1006l" in w for w in writes)
            )

            writes.clear()
            app.registry.execute("toggle_mouse")
            await pilot.pause()
            recaptured = (
                drv._mouse is True
                and any("1000h" in w for w in writes)
                and any("1006h" in w for w in writes)
            )
            return released, recaptured

    released, recaptured = _run(go())
    assert released
    assert recaptured


def test_default_capture_follows_terminal_capability() -> None:
    from unittest.mock import patch

    from markstar.app import _default_mouse_capture, _terminal_renders_pointer_shapes

    with patch.dict("os.environ", {"TERM": "xterm-256color"}, clear=True):
        assert _terminal_renders_pointer_shapes() is False  # VTE → I-beam default
        assert _default_mouse_capture() is False
    with patch.dict("os.environ", {"TERM": "xterm-kitty", "KITTY_WINDOW_ID": "1"}, clear=True):
        assert _terminal_renders_pointer_shapes() is True  # kitty → capture on

    # Windows: arrow pointer either way (ms/terminal#1441) → keep clicks.
    with patch("markstar.app.sys") as fake_sys:
        fake_sys.platform = "win32"
        with patch.dict("os.environ", {}, clear=True):
            assert _default_mouse_capture() is True


def test_toggle_survives_driver_without_methods() -> None:
    """Headless driver lacks the methods — the command must not crash."""

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.registry.execute("toggle_mouse")
            await pilot.pause()
            state_off = app._driver._mouse
            app.registry.execute("toggle_mouse")
            await pilot.pause()
            return state_off, app._driver._mouse

    off, on = _run(go())
    assert off is False
    assert on is True

"""Ctrl+C = copy (never quit) and cross-platform native clipboard dispatch."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from textual.widgets.text_area import Selection

from prose.app import ProseApp


def _run(coro):
    return asyncio.run(coro)


def test_ctrl_c_copies_selection_and_never_quits() -> None:
    async def go():
        app = ProseApp()
        toasts: list = []
        app.notify = lambda *a, **k: toasts.append((a, k))
        with patch.object(ProseApp, "_native_clipboard_copy") as native:
            async with app.run_test() as pilot:
                ed = app.query_one("#editor")
                ed.load_text("hello world")
                ed.selection = Selection((0, 0), (0, 5))
                await pilot.pause()
                await pilot.press("ctrl+c")
                await pilot.pause()
                copied = app._clipboard
                running = not app._exit
                native_called = native.called

                # Focus off text widgets (menu open): Ctrl+C stays a no-op.
                app.action_show_menu()
                await pilot.pause()
                await pilot.press("ctrl+c")
                await pilot.pause()
                return copied, running, native_called, toasts, app._exit

    copied, running, native_called, toasts, exited = _run(go())
    assert copied == "hello"
    assert running is True
    assert native_called is True
    assert exited is False
    assert not any("quit" in str(t).lower() for t in toasts)


def test_native_clipboard_platform_dispatch() -> None:
    calls: list = []
    with patch("subprocess.run", side_effect=lambda cmd, **k: calls.append(cmd)):
        # X11 branch (this dev machine / CI on Linux with DISPLAY + xclip)
        with patch.dict("os.environ", {"DISPLAY": ":1", "WAYLAND_DISPLAY": ""}):
            with patch("shutil.which", side_effect=lambda t: f"/usr/bin/{t}" if t == "xclip" else None):
                ProseApp._native_clipboard_copy("x")
    assert calls and calls[0][0] == "xclip"

    # Windows branch never probes Linux tools.
    calls.clear()
    with patch("subprocess.run", side_effect=lambda cmd, **k: calls.append(cmd)):
        with patch("prose.app.sys") as fake_sys:
            fake_sys.platform = "win32"
            ProseApp._native_clipboard_copy("x")
    assert calls == [["clip"]]

    # macOS branch uses pbcopy.
    calls.clear()
    with patch("subprocess.run", side_effect=lambda cmd, **k: calls.append(cmd)):
        with patch("prose.app.sys") as fake_sys:
            fake_sys.platform = "darwin"
            ProseApp._native_clipboard_copy("x")
    assert calls == [["pbcopy"]]

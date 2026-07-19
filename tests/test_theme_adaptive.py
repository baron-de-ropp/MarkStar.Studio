"""Mathematical dark/light detection + theme-adaptive color shifting."""

from __future__ import annotations

import asyncio

from markstar.app import MarkStarApp
from markstar.ui.themes import (
    contrast_shift,
    is_dark_color,
    relative_luminance,
    theme_is_dark,
)


def _run(coro):
    return asyncio.run(coro)


def test_luminance_endpoints() -> None:
    assert relative_luminance("#000000") == 0.0
    assert relative_luminance("#FFFFFF") == 1.0
    assert relative_luminance("#FFFFFF") > relative_luminance("#808080")


def test_is_dark_color() -> None:
    assert is_dark_color("#101216") is True
    assert is_dark_color("#F5F5F5") is False
    assert is_dark_color("#3a3a3a") is True


def test_theme_is_dark_detected_from_background() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.theme = "vscode-dark"
            await pilot.pause()
            dark = theme_is_dark(app)
            app.theme = "markstar-light"
            await pilot.pause()
            light = theme_is_dark(app)
            return dark, light

    dark, light = _run(go())
    assert dark is True
    assert light is False


def test_contrast_shift_flips_direction_with_theme() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.theme = "vscode-dark"
            await pilot.pause()
            on_dark = contrast_shift("#808080", 0.5, app)
            app.theme = "markstar-light"
            await pilot.pause()
            on_light = contrast_shift("#808080", 0.5, app)
            return on_dark, on_light

    on_dark, on_light = _run(go())
    # Dark theme lightens grey toward white; light theme darkens it toward black.
    assert relative_luminance(on_dark) > relative_luminance("#808080")
    assert relative_luminance(on_light) < relative_luminance("#808080")

"""Welcome screen: renders, and its folder choice becomes the project root."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from markstar import __version__
from markstar.app import MarkStarApp
from markstar.ui.project_panel import ProjectPanel
from markstar.ui.welcome import WelcomeScreen


def _run(coro):
    return asyncio.run(coro)


def test_welcome_logo_two_color_rows() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            screen = WelcomeScreen(app._project_root(), __version__)
            app.push_screen(screen)
            await pilot.pause()
            markup = screen._logo_markup()
            # Both theme colors present; six rows of block art.
            return markup

    markup = _run(go())
    assert markup.count("\n") == 5  # six rows
    assert "█" in markup and "[/]" in markup


def test_choosing_folder_sets_project_root(tmp_path) -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            with patch.object(
                app, "push_screen_wait", AsyncMock(return_value=tmp_path)
            ):
                await app._show_welcome()
            await pilot.pause()
            panel = app.query_one("#project-panel", ProjectPanel)
            return panel.is_open, app._project_root()

    is_open, root = _run(go())
    assert is_open is True
    assert root == tmp_path


def test_skipping_welcome_leaves_panel_closed() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            with patch.object(app, "push_screen_wait", AsyncMock(return_value=None)):
                await app._show_welcome()
            await pilot.pause()
            return app.query_one("#project-panel", ProjectPanel).is_open

    assert _run(go()) is False

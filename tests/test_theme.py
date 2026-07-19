"""Theme picker: registration, live-preview confirm, and cancel-revert."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from markstar.app import MarkStarApp
from markstar.ui.themes import ALL_THEMES, THEME_NAMES, token


def _run(coro):
    return asyncio.run(coro)


def test_all_themes_define_the_full_token_set() -> None:
    # Every theme must define the semantic tokens (so it looks right on its own,
    # not silently falling back to the base theme for core colors).
    required = {
        "hint-key", "tab-active", "tab-inactive", "rule", "search-match",
        "md-marker", "md-heading", "md-code", "md-link", "spell-underline",
    }
    for theme in ALL_THEMES:
        missing = required - set(theme.variables)
        assert not missing, f"{theme.name} missing tokens: {missing}"


def test_picker_confirm_applies_and_saves(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "config.toml"))

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            with patch.object(app, "push_screen_wait", AsyncMock(return_value="nord")):
                await app._theme_picker_async()
                await pilot.pause()
            return app.theme, app.prefs.theme, token(app, "md-heading")

    theme, saved, heading = _run(go())
    assert theme == "nord"
    assert saved == "nord"
    assert heading == "#81A1C1"  # nord blue, not the base theme's


def test_picker_cancel_reverts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "config.toml"))

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            before = app.theme
            with patch.object(app, "push_screen_wait", AsyncMock(return_value="")):
                await app._theme_picker_async()
                await pilot.pause()
            return before, app.theme

    before, after = _run(go())
    assert after == before  # cancelled → back to the original


def test_theme_names_are_registered() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            return set(app.available_themes)

    registered = _run(go())
    assert set(THEME_NAMES).issubset(registered)

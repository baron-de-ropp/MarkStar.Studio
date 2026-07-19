"""StarBot config screen: opens from the Project menu and Save persists."""

from __future__ import annotations

import asyncio

from textual.widgets import Button, Input

from markstar.ai.config import StarBotConfig
from markstar.app import MarkStarApp


def _run(coro):
    return asyncio.run(coro)


def test_project_menu_has_starbot() -> None:
    app = MarkStarApp()
    assert "Project" in app.registry.menu_names()
    assert "starbot_config" in app.registry


def test_screen_saves_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STARBOT_CONFIG", str(tmp_path / "sb.toml"))

    async def go():
        app = MarkStarApp()
        async with app.run_test(size=(100, 26)) as pilot:
            await pilot.pause()
            app.cmd_starbot_config()
            await pilot.pause()
            scr = app.screen
            scr.query_one("#sb-base", Input).value = "http://localhost:11434/v1"
            scr.query_one("#sb-model", Input).value = "llama3.1"
            scr.query_one("#sb-key", Input).value = "$OLLAMA_KEY"
            await pilot.pause()
            scr.query_one("#sb-save", Button).press()
            await pilot.pause()

    _run(go())
    saved = StarBotConfig.load()
    assert saved.base_url == "http://localhost:11434/v1"
    assert saved.model == "llama3.1"
    assert saved.api_key == "$OLLAMA_KEY"


def test_validate_needs_base_url_and_model(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STARBOT_CONFIG", str(tmp_path / "sb.toml"))

    async def go():
        app = MarkStarApp()
        async with app.run_test(size=(100, 26)) as pilot:
            await pilot.pause()
            app.cmd_starbot_config()
            await pilot.pause()
            scr = app.screen
            scr.query_one("#sb-validate", Button).press()  # empty fields
            await pilot.pause()
            from textual.widgets import Static

            return str(scr.query_one("#sb-results", Static).render())

    text = _run(go())
    assert "base URL" in text and "model" in text  # guarded before any network call

"""Interactive spelling bar: open, change, skip, add."""

from __future__ import annotations

import asyncio

from markstar.app import MarkStarApp, MarkStarTextArea
from markstar.ui.spell_bar import SpellBar


def _run(coro):
    return asyncio.run(coro)


def _app_with(text):
    async def prep(app, pilot):
        app._speller.prime()
        ed = app.query_one("#editor", MarkStarTextArea)
        ed.load_text(text)
        app.document.set_text(text)
        await pilot.pause()

    return prep


def test_open_focuses_first_misspelling() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await _app_with("The quikc brown fox")(app, pilot)
            app.cmd_spelling()
            await pilot.pause()
            bar = app.query_one("#spell-bar", SpellBar)
            return bar.is_visible, app._spell_current

    visible, current = _run(go())
    assert visible is True
    assert current[2] == "quikc"


def test_change_replaces_and_advances() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await _app_with("The quikc brown jumpd")(app, pilot)
            app.cmd_spelling()
            await pilot.pause()
            app._on_spell_requested(SpellBar.SpellRequested("change", "quick"))
            await pilot.pause()
            return app.document.text, app._spell_current

    text, current = _run(go())
    assert "quick brown" in text
    assert current[2] == "jumpd"  # advanced to the next misspelling


def test_skip_ignores_and_finishes() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await _app_with("The zzqword ends")(app, pilot)
            app.cmd_spelling()
            await pilot.pause()
            app._on_spell_requested(SpellBar.SpellRequested("skip", ""))
            await pilot.pause()
            bar = app.query_one("#spell-bar", SpellBar)
            return app._spell_current, bar.is_visible, app._speller.known("zzqword")

    current, visible, known = _run(go())
    assert current is None  # nothing left
    assert visible is False  # bar closed
    assert known is True  # ignored for the session


def test_add_persists_to_dictionary(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "config.toml"))

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await _app_with("Hello zzqword world")(app, pilot)
            app.cmd_spelling()
            await pilot.pause()
            app._on_spell_requested(SpellBar.SpellRequested("add", ""))
            await pilot.pause()
            return list(app.prefs.spell_added), app._speller.known("zzqword")

    added, known = _run(go())
    assert "zzqword" in added
    assert known is True

    from markstar.config import Preferences  # persisted across reload

    assert "zzqword" in Preferences.load().spell_added

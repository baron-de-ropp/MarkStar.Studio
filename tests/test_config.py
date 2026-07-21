"""Preferences persistence: TOML round-trip, resilience, and app application."""

from __future__ import annotations

import asyncio

from markstar.app import MarkStarApp, MarkStarTextArea
from markstar.config import Preferences, config_path


def _run(coro):
    return asyncio.run(coro)


def test_config_path_honors_env_override(tmp_path, monkeypatch) -> None:
    target = tmp_path / "custom.toml"
    monkeypatch.setenv("MARKSTAR_CONFIG", str(target))
    assert config_path() == target


def test_save_and_reload_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "config.toml"))
    Preferences(
        theme="markstar-light",
        mouse="off",
        formatting=False,
        soft_wrap=False,
        autosave=False,
        autosave_ms=3000,
        spellcheck_ms=250,
        spell_language="fr",
    ).save()

    reloaded = Preferences.load()
    assert reloaded.theme == "markstar-light"
    assert reloaded.mouse == "off"
    assert reloaded.formatting is False
    assert reloaded.soft_wrap is False
    assert reloaded.spellcheck_ms == 250
    assert reloaded.spell_language == "fr"
    # Regression: autosave + autosave_ms are written by _to_toml but were never
    # parsed back by load(), so toggling autosave off didn't survive a restart.
    assert reloaded.autosave is False
    assert reloaded.autosave_ms == 3000


def test_toml_is_human_readable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "config.toml"))
    Preferences(theme="markstar-light", formatting=False).save()
    text = (tmp_path / "config.toml").read_text()
    assert 'theme = "markstar-light"' in text
    assert "formatting = false" in text


def test_malformed_and_unknown_values_fall_back(tmp_path, monkeypatch) -> None:
    cfg = tmp_path / "config.toml"
    monkeypatch.setenv("MARKSTAR_CONFIG", str(cfg))

    cfg.write_text("this is not { valid toml ][")
    assert Preferences.load().theme == "vscode-dark"  # malformed → defaults

    cfg.write_text('theme = "does-not-exist"\nmouse = "sideways"\n')
    prefs = Preferences.load()
    assert prefs.theme == "vscode-dark"  # unknown theme ignored
    assert prefs.mouse == "auto"  # invalid mouse mode ignored


def test_app_applies_saved_prefs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "config.toml"))
    Preferences(
        theme="markstar-light", formatting=False, soft_wrap=False
    ).save()

    async def go():
        app = MarkStarApp(prefs=Preferences.load())
        async with app.run_test() as pilot:
            await pilot.pause()
            ed = app.query_one("#editor", MarkStarTextArea)
            return app.theme, ed.render_markdown, ed.soft_wrap

    theme, formatting, wrap = _run(go())
    assert theme == "markstar-light"
    assert formatting is False
    assert wrap is False


def test_recent_files_round_trip_and_cap(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "config.toml"))
    from markstar.config import RECENT_FILES_MAX

    files = [str(tmp_path / f"f{i}.md") for i in range(RECENT_FILES_MAX + 5)]
    Preferences(recent_files=files).save()

    loaded = Preferences.load().recent_files
    assert len(loaded) == RECENT_FILES_MAX          # over-long list is trimmed
    assert loaded == files[:RECENT_FILES_MAX]        # order preserved


def test_recent_files_defaults_to_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "missing.toml"))
    assert Preferences.load().recent_files == []

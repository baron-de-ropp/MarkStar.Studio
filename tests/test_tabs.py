"""Clickable tabs (activate + close) and configurable widths."""

from __future__ import annotations

import asyncio
from pathlib import Path

from markstar.app import MarkStarApp, MarkStarTextArea
from markstar.config import Preferences
from markstar.ui.project_panel import ProjectPanel


def _run(coro):
    return asyncio.run(coro)


def _two_tabs(tmp_path: Path):
    (tmp_path / "a.md").write_text("# A")
    (tmp_path / "b.md").write_text("# B")
    return tmp_path


def test_click_tab_activates_it(tmp_path) -> None:
    proj = _two_tabs(tmp_path)

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.workspace.open_path(proj / "a.md")
            app._load_active_into_editor()
            app.workspace.open_path(proj / "b.md")
            app._load_active_into_editor()
            app._refresh_status()
            await pilot.pause()
            was = app.workspace.active_index
            start = app._tab_bounds[0][0]
            app.handle_tab_click(start + 2)  # body of tab 0
            await pilot.pause()
            return was, app.workspace.active_index

    was, now = _run(go())
    assert was == 1 and now == 0


def test_click_close_x_closes_tab(tmp_path) -> None:
    proj = _two_tabs(tmp_path)

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.workspace.open_path(proj / "a.md")
            app._load_active_into_editor()
            app.workspace.open_path(proj / "b.md")
            app._load_active_into_editor()
            app._refresh_status()
            await pilot.pause()
            before = app.workspace.count
            close_col = app._tab_bounds[1][2]  # × of tab 1
            app.handle_tab_click(close_col)
            await pilot.pause()
            return before, app.workspace.count

    before, after = _run(go())
    assert before == 2 and after == 1


def test_configurable_widths_applied(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "config.toml"))
    Preferences(min_panel_width=50, prose_width=80).save()

    async def go():
        app = MarkStarApp(prefs=Preferences.load())
        # Narrow terminal so the margin can't grow the panel past its minimum.
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            ed = app.query_one("#editor", MarkStarTextArea)
            panel = app.query_one("#project-panel", ProjectPanel)
            return ed.prose_width, int(panel.styles.width.value)

    prose_width, panel_width = _run(go())
    assert prose_width == 80
    assert panel_width == 50  # floors at min on a narrow terminal


def test_panel_grows_to_fill_margin(tmp_path, monkeypatch) -> None:
    """On a wide terminal the panel fills the left margin minus a 5-col gap."""
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "config.toml"))
    Preferences(min_panel_width=40, prose_width=120).save()

    async def go():
        app = MarkStarApp(prefs=Preferences.load())
        async with app.run_test(size=(220, 24)) as pilot:
            await pilot.pause()
            margin = app._prose_margin()  # (220-120)//2 = 50
            panel = app.query_one("#project-panel", ProjectPanel)
            return margin, int(panel.styles.width.value)

    margin, panel_width = _run(go())
    assert margin == 50
    assert panel_width == 45  # margin - 5, above the 40 minimum


def test_prose_width_defaults_to_120(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "none.toml"))
    prefs = Preferences.load()
    assert prefs.prose_width == 120
    assert prefs.min_panel_width == 40  # new default


def test_prose_centering_margins() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test(size=(200, 24)) as pilot:
            await pilot.pause()
            wide = app._prose_margin()  # (200-120)//2 = 40
            app.cmd_toggle_center()
            await pilot.pause()
            off = app._prose_margin()  # base 5
            return wide, off

    wide, off = _run(go())
    assert wide == 40
    assert off == 5


def test_narrow_terminal_floors_margin() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test(size=(100, 24)) as pilot:
            await pilot.pause()
            return app._prose_margin()

    assert _run(go()) == 5  # (100-120)//2 negative → floor at base


def test_opening_same_document_twice_reuses_tab(tmp_path) -> None:
    (tmp_path / "a.md").write_text("# A")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.workspace.open_path(tmp_path / "a.md")
            app._load_active_into_editor()
            app.workspace.open_path(tmp_path / "a.md")  # same file again
            app._load_active_into_editor()
            await pilot.pause()
            return app.workspace.count

    assert _run(go()) == 1

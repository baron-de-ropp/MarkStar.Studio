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


def test_prose_width_pref_applied_to_editor(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "config.toml"))
    Preferences(prose_width=80).save()

    async def go():
        app = MarkStarApp(prefs=Preferences.load())
        async with app.run_test(size=(120, 24)) as pilot:
            await pilot.pause()
            return app.query_one("#editor", MarkStarTextArea).prose_width

    assert _run(go()) == 80


def test_layout_keeps_prose_clear_of_the_panel() -> None:
    """Editor + tabs must start at/after the panel's right edge at every size."""

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            results = []
            for width, panel_open in [
                (160, True), (120, True), (76, True), (50, True), (40, True),
                (100, False),
            ]:
                panel, left_pad, col, right_pad = app._compute_layout(width, panel_open)
                available = width - panel
                results.append((width, panel_open, panel, left_pad, col, right_pad, available))
            return results

    for width, panel_open, panel, left_pad, col, right_pad, available in _run(go()):
        assert left_pad >= panel, f"{width}: editor hidden under panel"
        assert col >= 1
        assert left_pad + col + right_pad == width, f"{width}: columns don't sum"
        assert col <= available, f"{width}: prose wider than available space"
        if panel_open:
            assert panel <= width - 24, f"{width}: panel eats the screen"


def test_centering_narrows_and_toggle_off_widens() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test(size=(200, 24)) as pilot:
            await pilot.pause()
            _, _, col_centered, _ = app._compute_layout(200, False)  # 120 cap
            app.cmd_toggle_center()
            await pilot.pause()
            _, _, col_full, _ = app._compute_layout(200, False)
            return col_centered, col_full

    centered, full = _run(go())
    assert centered == 120  # capped at prose_width, centered
    assert full == 190  # not centered → fills (200 - 2*5)


def test_prose_width_defaults_to_120(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "none.toml"))
    prefs = Preferences.load()
    assert prefs.prose_width == 120
    assert prefs.min_panel_width == 40  # new default


def test_zen_hides_content_but_keeps_rules_and_dimensions() -> None:
    """Zen empties the tab chips + footer text but leaves the strips (and their
    rule lines) in place, so the prose frame doesn't shift."""

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            label = app.query_one("#tab-label")
            hints = app.query_one("#support-hints")
            strip = app.query_one("#tab-strip")
            rule = app.query_one("#tab-rule")
            before = (label.visible, hints.visible)
            app.cmd_toggle_zen()
            await pilot.pause()
            during = (label.visible, hints.visible, strip.display, rule.display)
            app.cmd_toggle_zen()
            await pilot.pause()
            after = (label.visible, hints.visible)
            return before, during, after

    before, during, after = _run(go())
    assert before == (True, True)
    # content hidden, but the strip and its rule stay on screen
    assert during == (False, False, True, True)
    assert after == (True, True)


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

"""Clickable tabs (activate + close) and configurable widths."""

from __future__ import annotations

import asyncio
from pathlib import Path

from markstar.app import MarkStarApp, MarkStarTextArea
from markstar.config import Preferences
from markstar.ui.project_panel import ProjectPanel
from markstar.ui.tab_bar import TabBar


def _run(coro):
    return asyncio.run(coro)


class _Click:
    """Minimal stand-in for a Click event — TabBar.on_click only reads .x."""

    def __init__(self, x: int) -> None:
        self.x = x


def _two_tabs(tmp_path: Path):
    (tmp_path / "a.md").write_text("# A")
    (tmp_path / "b.md").write_text("# B")
    return tmp_path


def _open_two(app, proj):
    app.workspace.open_path(proj / "a.md")
    app._load_active_into_editor()
    app.workspace.open_path(proj / "b.md")
    app._load_active_into_editor()
    app._refresh_status()


def test_click_tab_activates_it(tmp_path) -> None:
    proj = _two_tabs(tmp_path)

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            _open_two(app, proj)
            await pilot.pause()
            was = app.workspace.active_index
            bar = app.query_one("#tab-label", TabBar)
            start = bar._bounds[0][0]
            assert bar.hit_test(start + 2) == ("activate", 0)
            bar.on_click(_Click(start + 2))  # body of tab 0
            await pilot.pause()
            return was, app.workspace.active_index

    was, now = _run(go())
    assert was == 1 and now == 0


def test_click_close_x_closes_tab(tmp_path) -> None:
    proj = _two_tabs(tmp_path)

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            _open_two(app, proj)
            await pilot.pause()
            before = app.workspace.count
            bar = app.query_one("#tab-label", TabBar)
            close_col = bar._bounds[1][2]  # × of tab 1
            assert bar.hit_test(close_col) == ("close", 1)
            bar.on_click(_Click(close_col))
            await pilot.pause()
            return before, app.workspace.count

    before, after = _run(go())
    assert before == 2 and after == 1


def test_click_outside_any_chip_is_a_noop(tmp_path) -> None:
    proj = _two_tabs(tmp_path)

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            _open_two(app, proj)
            await pilot.pause()
            bar = app.query_one("#tab-label", TabBar)
            far = bar._bounds[-1][1] + 50  # well past the last chip
            assert bar.hit_test(far) is None
            active = app.workspace.active_index
            bar.on_click(_Click(far))
            await pilot.pause()
            return active, app.workspace.active_index, app.workspace.count

    active, still, count = _run(go())
    assert still == active and count == 2


def test_prose_width_pref_applied_to_editor(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "config.toml"))
    Preferences(prose_width=80).save()

    async def go():
        app = MarkStarApp(prefs=Preferences.load())
        async with app.run_test(size=(120, 24)) as pilot:
            await pilot.pause()
            return app.query_one("#editor", MarkStarTextArea).prose_width

    assert _run(go()) == 80


def test_prose_centered_in_full_width_panel_overlays() -> None:
    """The panel is an overlay — it must NOT reserve width. The prose column is
    centered in the full window whether the panel is open or closed (so opening
    the panel never shifts the prose off-center); the panel just floats on top."""

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            results = []
            for width in [160, 120, 100, 76, 50, 40]:
                closed = app._compute_layout(width, False)
                opened = app._compute_layout(width, True)
                results.append((width, closed, opened))
            return results

    for width, closed, opened in _run(go()):
        panel_c, left_c, col_c, right_c = closed
        panel_o, left_o, col_o, right_o = opened
        # Columns always tile the full width.
        assert left_c + col_c + right_c == width
        assert left_o + col_o + right_o == width
        # Opening the panel does not move the prose: same padding + column.
        assert (left_o, col_o, right_o) == (left_c, col_c, right_c), (
            f"{width}: panel shifted the prose instead of overlaying"
        )
        assert panel_c == 0 and panel_o > 0


def test_shrinking_from_large_updates_rules_same_frame() -> None:
    """Resizing down from a big window must relayout to the NEW width immediately —
    not lag one resize behind (which left the rules/padding at the old width)."""

    async def go():
        app = MarkStarApp()
        async with app.run_test(size=(220, 50)) as pilot:
            await pilot.pause()
            await pilot.pause()
            await pilot.resize_terminal(130, 35)
            for _ in range(6):
                await pilot.pause()
            strip = app.query_one("#tab-strip")
            rule = app.query_one("#tab-rule")
            return app.size.width, strip.styles.padding.left, rule.size.width

    width, pad_left, rule_w = _run(go())
    assert width == 130
    # 130 wide, centered, base inset 5 → prose column 120, pad 5 each side.
    assert pad_left == 5, f"padding lagged the resize (left={pad_left})"
    assert rule_w == 120, f"rule width lagged the resize (w={rule_w})"


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

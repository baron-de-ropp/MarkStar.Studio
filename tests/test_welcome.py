"""Welcome screen: renders, and its folder choice becomes the project root."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from markstar import __version__
from markstar.app import MarkStarApp
from markstar.ui.project_panel import ProjectPanel
from markstar.ui.welcome import (
    TAB_FILES,
    TAB_NEW,
    TAB_PROJECTS,
    WelcomeChoice,
    WelcomeScreen,
    _LOGO_MIN_WIDTH,
)


def _run(coro):
    return asyncio.run(coro)


def test_welcome_logo_compacts_on_narrow_terminal() -> None:
    """Below the block-logo width the welcome shows a one-line wordmark instead of
    the multi-line ANSI logo (which would wrap/clip), and swaps back when widened."""

    async def go():
        app = MarkStarApp()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            scr = WelcomeScreen(app._project_root(), __version__, [])
            await app.push_screen(scr)
            await pilot.pause()
            logo = scr.query_one("#welcome-logo")
            # The markup the two modes produce: block logo is multi-line, the
            # compact wordmark is a single line.
            wide_lines = scr._logo_markup(compact=False).count("\n")
            narrow_lines = scr._logo_markup(compact=True).count("\n")
            wide_compact = logo.has_class("compact")

            await pilot.resize_terminal(_LOGO_MIN_WIDTH - 20, 32)
            for _ in range(4):
                await pilot.pause()
            narrow_compact = logo.has_class("compact")

            await pilot.resize_terminal(100, 32)
            for _ in range(4):
                await pilot.pause()
            restored_compact = logo.has_class("compact")
            return (
                wide_compact, wide_lines,
                narrow_compact, narrow_lines,
                restored_compact,
            )

    wide_c, wide_l, narrow_c, narrow_l, restored_c = _run(go())
    assert wide_c is False and wide_l >= 5      # full multi-line block logo
    assert narrow_c is True and narrow_l == 0   # single-line wordmark
    assert restored_c is False                  # swaps back when widened


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
                app,
                "push_screen_wait",
                AsyncMock(return_value=WelcomeChoice("folder", tmp_path)),
            ):
                await app._show_welcome()
            await pilot.pause()
            panel = app.query_one("#project-panel", ProjectPanel)
            return panel.is_open, app._project_root()

    is_open, root = _run(go())
    assert is_open is True
    assert root == tmp_path


def test_recent_projects_recorded_dedup_and_capped(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "cfg.toml"))
    dirs = [tmp_path / f"p{i}" for i in range(7)]
    for d in dirs:
        d.mkdir()

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            for d in dirs:
                app._set_project_root(d)
            app._set_project_root(dirs[6])  # re-open newest (dedup)
            await pilot.pause()
            return list(app.prefs.recent_projects)

    recents = _run(go())
    assert len(recents) == 5  # capped
    assert recents[0] == str(dirs[6].resolve())  # most recent first
    assert recents.count(str(dirs[6].resolve())) == 1  # deduped

    from markstar.config import Preferences  # persisted + reloads

    assert Preferences.load().recent_projects == recents


def test_file_launch_opens_editor_and_panel_at_folder(tmp_path) -> None:
    (tmp_path / "chapter.md").write_text("# Chapter")

    async def go():
        app = MarkStarApp(path=tmp_path / "chapter.md")
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one("#project-panel", ProjectPanel)
            return app.document.path, panel.is_open, app._project_root()

    doc_path, panel_open, root = _run(go())
    assert doc_path == tmp_path / "chapter.md"
    assert panel_open is True
    assert root == tmp_path


def test_nonexistent_folder_offers_to_create(tmp_path) -> None:
    """Typing a non-existent folder → confirm → the folder is created + opened."""
    new_dir = tmp_path / "BrandNewNovel"
    assert not new_dir.exists()

    async def go():
        from unittest.mock import AsyncMock, patch

        app = MarkStarApp()
        async with app.run_test() as pilot:
            # welcome returns the missing path; then the confirm dialog says yes.
            with patch.object(
                app,
                "push_screen_wait",
                AsyncMock(side_effect=[WelcomeChoice("folder", new_dir), True]),
            ):
                await app._show_welcome()
            await pilot.pause()
            return new_dir.is_dir(), app._project_root()

    created, root = _run(go())
    assert created is True
    assert root == new_dir


def test_declining_create_leaves_no_folder(tmp_path) -> None:
    new_dir = tmp_path / "Nope"

    async def go():
        from unittest.mock import AsyncMock, patch

        app = MarkStarApp()
        async with app.run_test() as pilot:
            with patch.object(
                app,
                "push_screen_wait",
                AsyncMock(side_effect=[WelcomeChoice("folder", new_dir), False]),
            ):
                await app._show_welcome()
            await pilot.pause()
            return new_dir.exists()

    assert _run(go()) is False


def test_skipping_welcome_leaves_panel_closed() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            with patch.object(app, "push_screen_wait", AsyncMock(return_value=None)):
                await app._show_welcome()
            await pilot.pause()
            return app.query_one("#project-panel", ProjectPanel).is_open

    assert _run(go()) is False


# ---- the reserved well ------------------------------------------------------


def _tab_geometry(width: int, height: int):
    """Box height and top row on each tab, at a given terminal size."""

    async def go():
        app = MarkStarApp()
        async with app.run_test(size=(width, height)) as pilot:
            await pilot.pause()
            scr = WelcomeScreen(
                Path("/tmp"),
                __version__,
                [Path(f"/tmp/project-{n}") for n in range(5)],
                [(Path(f"/tmp/chapter-{i}.md"), 0.0) for i in range(1, 8)],
                session_count=3,
            )
            await app.push_screen(scr)
            for _ in range(6):
                await pilot.pause()
            out = {}
            for tab in (TAB_FILES, TAB_PROJECTS, TAB_NEW):
                scr._show_tab(tab)
                for _ in range(6):
                    await pilot.pause()
                region = scr.query_one("#welcome-box").region
                out[tab] = (region.height, region.y)
            return out

    return _run(go())


def test_logo_does_not_move_between_tabs() -> None:
    """The tabs hold very different amounts (1 row vs. 6 + a path field). The
    well under the tab strip is a fixed reservation so the box cannot breathe
    and drag the logo up and down as you arrow across."""
    geo = _tab_geometry(100, 40)
    assert len(set(geo.values())) == 1, f"box moves between tabs: {geo}"


def test_well_shrinks_rather_than_overflowing_a_short_terminal() -> None:
    """Reserved, not guaranteed: on a 24-row terminal the well gives back rows
    so the hint line and the top of the logo stay on screen."""
    height = 24
    geo = _tab_geometry(100, height)
    assert len(set(geo.values())) == 1, f"box moves between tabs: {geo}"
    box_height, top = next(iter(geo.values()))
    assert top >= 0 and top + box_height <= height, (
        f"box ({box_height} rows at row {top}) overflows a {height}-row terminal"
    )

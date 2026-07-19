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
                app, "push_screen_wait", AsyncMock(side_effect=[new_dir, True])
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
                app, "push_screen_wait", AsyncMock(side_effect=[new_dir, False])
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

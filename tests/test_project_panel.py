"""Project panel: filter, toggle, open-into-tab, folder launch, Esc-close."""

from __future__ import annotations

import asyncio
from pathlib import Path

from markstar.app import MarkStarApp
from markstar.ui.project_panel import ProjectPanel, WriterTree


def _run(coro):
    return asyncio.run(coro)


def _make_project(tmp_path: Path) -> Path:
    (tmp_path / "chapter-01.md").write_text("# One")
    (tmp_path / "chapter-02.md").write_text("# Two")
    (tmp_path / "notes.txt").write_text("notes")
    (tmp_path / "cover.png").write_bytes(b"x")
    (tmp_path / ".secret.md").write_text("hidden")
    (tmp_path / "sub").mkdir()
    return tmp_path


def test_tree_shows_all_files_but_hides_dotfiles(tmp_path) -> None:
    proj = _make_project(tmp_path)

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.cmd_toggle_project_panel()
            await pilot.pause()
            tree = app.query_one(WriterTree)
            return sorted(p.name for p in tree.filter_paths(list(proj.iterdir())))

    names = _run(go())
    # All non-hidden entries (incl. images/assets), dotfiles excluded.
    assert names == ["chapter-01.md", "chapter-02.md", "cover.png", "notes.txt", "sub"]
    assert ".secret.md" not in names


def test_toggle_and_esc(tmp_path) -> None:
    async def go():
        app = MarkStarApp()  # no path → cwd, panel closed
        async with app.run_test() as pilot:
            panel = app.query_one("#project-panel", ProjectPanel)
            start_closed = not panel.is_open
            app.cmd_toggle_project_panel()
            await pilot.pause()
            opened = panel.is_open
            app.action_esc_key()
            await pilot.pause()
            closed_by_esc = not panel.is_open
            return start_closed, opened, closed_by_esc

    start_closed, opened, closed_by_esc = _run(go())
    assert start_closed and opened and closed_by_esc


def test_launch_with_folder_opens_panel(tmp_path) -> None:
    proj = _make_project(tmp_path)

    async def go():
        app = MarkStarApp(path=proj)
        async with app.run_test() as pilot:
            await pilot.pause()
            return app._project_root(), app.query_one("#project-panel", ProjectPanel).is_open

    root, is_open = _run(go())
    assert root == proj
    assert is_open is True


def test_selecting_file_opens_it_in_tab(tmp_path) -> None:
    proj = _make_project(tmp_path)

    async def go():
        app = MarkStarApp(path=proj)
        async with app.run_test() as pilot:
            await pilot.pause()
            event = type("E", (), {"path": proj / "chapter-02.md", "stop": lambda self: None})()
            app._on_tree_file_selected(event)
            await pilot.pause()
            return app.document.path, app.query_one("#editor").text

    path, text = _run(go())
    assert path == proj / "chapter-02.md"
    assert text.startswith("# Two")

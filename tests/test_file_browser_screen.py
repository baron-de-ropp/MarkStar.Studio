"""File browser modal: navigate folders and confirm a path."""

from __future__ import annotations

import asyncio
from pathlib import Path

from markstar.app import MarkStarApp
from markstar.ui.file_browser import FileBrowserScreen


def _run(coro):
    return asyncio.run(coro)


async def _settle(pilot, times: int = 6) -> None:
    for _ in range(times):
        await pilot.pause()


def test_folder_mode_use_this_folder(tmp_path: Path) -> None:
    (tmp_path / "ch1.md").write_text("x", encoding="utf-8")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            screen = FileBrowserScreen("Open Folder", mode="folder", start=tmp_path)
            app.push_screen(screen)
            await _settle(pilot)
            result: list = []
            screen.dismiss = lambda v: result.append(v)  # type: ignore[method-assign]
            screen._confirm_from_list()
            return result

    assert [Path(p).resolve() for p in _run(go())] == [tmp_path.resolve()]


def test_file_mode_opens_markdown(tmp_path: Path) -> None:
    target = tmp_path / "ch1.md"
    target.write_text("hello", encoding="utf-8")
    (tmp_path / "notes").mkdir()

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            screen = FileBrowserScreen("Open File", mode="file", start=tmp_path)
            app.push_screen(screen)
            await _settle(pilot)
            # Highlight the markdown file row (after .. and notes/)
            ol = screen.query_one("#fb-list")
            # Find the option id for ch1.md
            for i, entry in enumerate(screen._entries):
                if entry.name == "ch1.md":
                    ol.highlighted = i + 0  # ids match entry indices; no ::cwd in file mode
                    # Account for no leading special row in file mode
                    break
            # highlighted indexes the option list; entry index == option id in file mode
            for idx in range(ol.option_count):
                opt = ol.get_option_at_index(idx)
                if opt.id is not None and opt.id.isdigit():
                    if screen._entries[int(opt.id)].name == "ch1.md":
                        ol.highlighted = idx
                        break
            result: list = []
            screen.dismiss = lambda v: result.append(v)  # type: ignore[method-assign]
            screen._confirm_from_list()
            return result

    assert [Path(p).resolve() for p in _run(go())] == [target.resolve()]


def test_escape_cancels(tmp_path: Path) -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            screen = FileBrowserScreen("Open", mode="file", start=tmp_path)
            app.push_screen(screen)
            await _settle(pilot)
            result: list = []
            screen.dismiss = lambda v: result.append(v)  # type: ignore[method-assign]
            screen.action_cancel()
            return result

    assert _run(go()) == [None]


def test_enter_on_dir_navigates(tmp_path: Path) -> None:
    child = tmp_path / "chapters"
    child.mkdir()
    (child / "one.md").write_text("x", encoding="utf-8")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            screen = FileBrowserScreen("Open", mode="file", start=tmp_path)
            app.push_screen(screen)
            await _settle(pilot)
            for idx in range(screen.query_one("#fb-list").option_count):
                opt = screen.query_one("#fb-list").get_option_at_index(idx)
                if opt.id is not None and opt.id.isdigit():
                    if screen._entries[int(opt.id)].name == "chapters":
                        screen.query_one("#fb-list").highlighted = idx
                        break
            screen._confirm_from_list()
            await _settle(pilot)
            return screen._cwd, [e.name for e in screen._entries if not e.is_parent]

    cwd, names = _run(go())
    assert cwd.resolve() == child.resolve()
    assert "one.md" in names

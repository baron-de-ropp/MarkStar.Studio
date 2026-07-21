"""Quick Open (Ctrl+O): fuzzy picking, literal paths, and recents bookkeeping."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from markstar.app import MarkStarApp
from markstar.ui.quick_open import QuickOpenScreen


def _run(coro):
    return asyncio.run(coro)


async def _settle(pilot, times: int = 6) -> None:
    for _ in range(times):
        await pilot.pause()


# ---- the screen itself ------------------------------------------------------


def test_recents_are_listed_immediately(tmp_path: Path) -> None:
    a = tmp_path / "chapter-3.md"
    a.write_text("x", encoding="utf-8")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            screen = QuickOpenScreen([str(a)], None)
            app.push_screen(screen)
            await _settle(pilot)
            return list(screen._rows)

    assert _run(go()) == [str(tmp_path / "chapter-3.md")]


def test_typing_filters_the_list(tmp_path: Path) -> None:
    for name in ("chapter-3.md", "outline.md", "characters.md"):
        (tmp_path / name).write_text("x", encoding="utf-8")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            screen = QuickOpenScreen([], tmp_path)
            app.push_screen(screen)
            await _settle(pilot, 12)  # let the project scan land
            screen._populate("ch3")
            return list(screen._rows)

    rows = _run(go())
    assert rows == ["chapter-3.md"]


def test_literal_prefix_switches_to_path_mode() -> None:
    assert QuickOpenScreen._is_literal("/etc/x.md")
    assert QuickOpenScreen._is_literal("~/notes.md")
    assert QuickOpenScreen._is_literal("./draft.md")
    assert not QuickOpenScreen._is_literal("chapter")


def test_literal_path_submits_expanded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            screen = QuickOpenScreen([], None)
            app.push_screen(screen)
            await _settle(pilot)
            screen.query_one("#qo-input").value = "~/typed.md"
            result: list = []
            screen.dismiss = lambda v: result.append(v)  # type: ignore[method-assign]
            screen.action_submit()
            return result

    assert _run(go()) == [tmp_path / "typed.md"]


def test_escape_returns_nothing() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            screen = QuickOpenScreen([], None)
            app.push_screen(screen)
            await _settle(pilot)
            result: list = []
            screen.dismiss = lambda v: result.append(v)  # type: ignore[method-assign]
            screen.action_cancel()
            return result

    assert _run(go()) == [None]


# ---- app wiring -------------------------------------------------------------


def test_picking_a_file_opens_it(tmp_path: Path) -> None:
    target = tmp_path / "picked.md"
    target.write_text("# Picked", encoding="utf-8")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            with patch.object(
                app, "push_screen_wait", AsyncMock(return_value=target)
            ):
                app.cmd_open_file()
                await _settle(pilot)
            return app.document.path, app.document.text

    path, text = _run(go())
    assert path == target
    assert text.startswith("# Picked")


def test_opening_records_a_recent_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "cfg.toml"))
    target = tmp_path / "remembered.md"
    target.write_text("x", encoding="utf-8")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app._open_doc(target)
            await pilot.pause()
            return list(app.prefs.recent_files)

    recents = _run(go())
    assert recents == [str(target.resolve())]


def test_stale_recent_is_reported_and_pruned(tmp_path: Path, monkeypatch) -> None:
    """A file that moved should say so, not become an empty buffer."""
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "cfg.toml"))
    gone = tmp_path / "vanished.md"

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.prefs.recent_files = [str(gone)]
            opened = app._open_doc(gone, must_exist=True)
            await pilot.pause()
            return opened, list(app.prefs.recent_files), app.document.path

    opened, recents, doc_path = _run(go())
    assert opened is False
    assert recents == []       # pruned
    assert doc_path is None    # nothing was opened


def test_typed_missing_path_still_creates_a_buffer(tmp_path: Path) -> None:
    """Naming a file that isn't there yet is how you create one."""
    fresh = tmp_path / "brand-new.md"

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            opened = app._open_doc(fresh)  # must_exist defaults to False
            await pilot.pause()
            return opened, app.document.path

    opened, path = _run(go())
    assert opened is True
    assert path == fresh

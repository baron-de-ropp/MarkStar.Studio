"""PathInput widget: Tab completes/cycles paths and never steals focus away."""

from __future__ import annotations

import asyncio
import os

from textual.app import App, ComposeResult

from markstar.ui.path_input import PathInput


def _run(coro):
    return asyncio.run(coro)


def _make(tmp_path):
    (tmp_path / "chapters").mkdir()
    (tmp_path / "characters").mkdir()
    (tmp_path / "chapter-notes.md").write_text("x")
    return tmp_path


class _OneInput(App):
    def compose(self) -> ComposeResult:
        yield PathInput(id="p")


class _TwoInputs(App):
    def compose(self) -> ComposeResult:
        yield PathInput(id="a")
        yield PathInput(id="b")


def test_tab_extends_to_common_prefix(tmp_path) -> None:
    _make(tmp_path)

    async def go():
        app = _OneInput()
        async with app.run_test() as pilot:
            inp = app.query_one("#p", PathInput)
            inp.focus()
            inp.value = str(tmp_path / "ch")
            inp.cursor_position = len(inp.value)
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            return inp.value

    assert _run(go()) == str(tmp_path / "cha")


def test_tab_cycles_candidates_at_branch_point(tmp_path) -> None:
    _make(tmp_path)

    async def go():
        app = _OneInput()
        async with app.run_test() as pilot:
            inp = app.query_one("#p", PathInput)
            inp.focus()
            inp.value = str(tmp_path / "cha")  # already the common prefix
            inp.cursor_position = len(inp.value)
            await pilot.pause()
            seen = []
            for _ in range(4):
                await pilot.press("tab")
                await pilot.pause()
                seen.append(os.path.basename(inp.value.rstrip(os.sep)))
            return seen

    seen = _run(go())
    # Cycles through the three candidates, then wraps.
    assert seen == ["chapter-notes.md", "chapters", "characters", "chapter-notes.md"]


def test_tab_does_not_move_focus(tmp_path) -> None:
    _make(tmp_path)

    async def go():
        app = _TwoInputs()
        async with app.run_test() as pilot:
            a = app.query_one("#a", PathInput)
            a.focus()
            a.value = str(tmp_path / "ch")
            a.cursor_position = len(a.value)
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            return app.focused.id

    assert _run(go()) == "a"  # focus stayed on the path field, didn't tab away

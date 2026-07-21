"""Tab cycling: F6/Shift+F6 primary, Ctrl+PageUp/Down as pass-through aliases.

GNOME Terminal (and other VTE terminals) bind Ctrl+PageUp/PageDown to their own
tabs, so those never reach the app there. A bare F-key is one unambiguous escape
sequence that no terminal rewrites, which is why it is the advertised route.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from markstar.app import MarkStarApp


def _run(coro):
    return asyncio.run(coro)


def _seed(tmp_path: Path) -> list[Path]:
    paths = []
    for name in ("a", "b", "c"):
        p = tmp_path / f"{name}.md"
        p.write_text(f"# {name}\n", encoding="utf-8")
        paths.append(p)
    return paths


async def _open_three(app, pilot, paths):
    """Open a.md, b.md, c.md and park on the FIRST tab.

    Pinning the starting tab keeps these assertions about cycling rather than
    about whatever tab happened to be active after opening.
    """
    for p in paths:
        app._open_doc(p)
    app.workspace.set_active(0)
    app._load_active_into_editor()
    for _ in range(3):
        await pilot.pause()


def _active(app) -> str:
    p = app.workspace.active.path
    return p.name if p else "Untitled"


def test_f6_cycles_forward_and_wraps(tmp_path: Path) -> None:
    paths = _seed(tmp_path)

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await _open_three(app, pilot, paths)
            seen = []
            for _ in range(4):
                await pilot.press("f6")
                await pilot.pause()
                seen.append(_active(app))
            return seen

    # Wrapping matters: F6 alone can reach every tab even if Shift+F6 is lost.
    assert _run(go()) == ["b.md", "c.md", "a.md", "b.md"]


def test_shift_f6_cycles_backward(tmp_path: Path) -> None:
    paths = _seed(tmp_path)

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await _open_three(app, pilot, paths)
            seen = []
            for _ in range(3):
                await pilot.press("shift+f6")
                await pilot.pause()
                seen.append(_active(app))
            return seen

    # from a.md, backwards wraps to the end first
    assert _run(go()) == ["c.md", "b.md", "a.md"]


def test_ctrl_pagedown_still_works_where_it_arrives(tmp_path: Path) -> None:
    paths = _seed(tmp_path)

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await _open_three(app, pilot, paths)
            await pilot.press("ctrl+pagedown")
            await pilot.pause()
            return _active(app)

    assert _run(go()) == "b.md"  # a.md -> b.md


def test_menu_advertises_the_reliable_key() -> None:
    """The menu must not promise a key the terminal eats."""

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            return {c.id: c.binding for c in app.registry if c.id in ("next_tab", "prev_tab")}

    bindings = _run(go())
    assert bindings["next_tab"] == "f6"
    assert bindings["prev_tab"] == "shift+f6"

"""propose_edit tool + the accept / reject / stale apply flow."""

from __future__ import annotations

import asyncio
import json

from markstar.ai.edits import EditProposal, extract_lines
from markstar.ai.tools import ProjectTools
from markstar.app import MarkStarApp
from markstar.ui.edit_card import EditCard


def _run(coro):
    return asyncio.run(coro)


# --- tool level ------------------------------------------------------------


def test_extract_lines() -> None:
    assert extract_lines("a\nb\nc", 2, 2) == "b"
    assert extract_lines("a\nb\nc", 1, 2) == "a\nb"
    assert extract_lines("a\nb\nc", 5, 6) == ""


def test_propose_edit_registers_proposal(tmp_path) -> None:
    (tmp_path / "a.md").write_text("line one\nline two\nline three")
    captured = []
    tools = ProjectTools(tmp_path, on_proposal=captured.append)
    out = tools.execute(
        "propose_edit",
        json.dumps(
            {"path": "a.md", "start_line": 2, "end_line": 2,
             "new_text": "LINE TWO", "reason": "caps"}
        ),
    )
    assert "Proposed edit #1" in out
    assert len(captured) == 1
    p = captured[0]
    assert (p.path, p.start_line, p.end_line) == ("a.md", 2, 2)
    assert p.old_text == "line two" and p.new_text == "LINE TWO"
    assert p.reason == "caps"


def test_propose_edit_missing_file(tmp_path) -> None:
    tools = ProjectTools(tmp_path)
    out = tools.execute(
        "propose_edit",
        json.dumps({"path": "nope.md", "start_line": 1, "end_line": 1,
                    "new_text": "x", "reason": "r"}),
    )
    assert "no such file" in out


def test_edit_tool_is_advertised() -> None:
    from markstar.ai.tools import TOOL_SPECS

    names = {s["function"]["name"] for s in TOOL_SPECS}
    assert "propose_edit" in names


# --- app apply flow --------------------------------------------------------


def _app_with_project(tmp_path):
    async def _open(app, pilot):
        await pilot.pause()
        app._project_root = lambda: tmp_path
        app.cmd_toggle_starbot()
        await pilot.pause()

    return _open


def test_accept_applies_edit_to_buffer(tmp_path) -> None:
    (tmp_path / "a.md").write_text("line one\nline two\nline three")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await _app_with_project(tmp_path)(app, pilot)
            prop = EditProposal(1, "a.md", 2, 2, "LINE TWO", "caps", "line two")
            app._on_starbot_proposal(prop)
            await pilot.pause()
            app._on_edit_accepted(EditCard.Accepted(1))
            await pilot.pause()
            return app.query_one("#editor").text, app.document.path.name

    text, name = _run(go())
    assert text == "line one\nLINE TWO\nline three"
    assert name == "a.md"


def test_reject_leaves_file_and_buffer_unchanged(tmp_path) -> None:
    (tmp_path / "a.md").write_text("line one\nline two")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await _app_with_project(tmp_path)(app, pilot)
            prop = EditProposal(1, "a.md", 1, 1, "CHANGED", "x", "line one")
            app._on_starbot_proposal(prop)
            await pilot.pause()
            app._on_edit_rejected(EditCard.Rejected(1))
            await pilot.pause()
            return (tmp_path / "a.md").read_text()

    assert _run(go()) == "line one\nline two"  # nothing applied


def test_stale_proposal_is_refused(tmp_path) -> None:
    (tmp_path / "a.md").write_text("line one\nline two")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await _app_with_project(tmp_path)(app, pilot)
            # old_text doesn't match the real line 1 → stale, must not apply.
            prop = EditProposal(1, "a.md", 1, 1, "CHANGED", "x", "SOMETHING ELSE")
            return app._apply_proposal(prop)

    assert _run(go()) is False

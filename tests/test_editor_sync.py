"""Characterization tests for the Document <-> editor sync invariant.

These lock in the behavior the EditorSession seam guarantees, so future refactors
of the sync path can't silently regress it: reads of self.document always reflect
the live editor, and switching tabs never loses unsaved edits.
"""

from __future__ import annotations

import asyncio

from markstar.app import MarkStarApp


def _run(coro):
    return asyncio.run(coro)


def test_document_reflects_live_editor_before_change_event_processes() -> None:
    """The whole point of the seam: read self.document right after an editor edit,
    WITHOUT pumping the message loop, and it's already current — no manual sync."""

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            ed = app.query_one("#editor")
            ed.load_text("start")
            await pilot.pause()
            # Edit the editor but do NOT pause — the Changed event is queued,
            # not yet processed, so the Document would be stale without auto-flush.
            ed.insert(" MORE", location=(0, 5))
            return app.document.text  # reading self.document must flush first

    assert _run(go()) == "start MORE"


def test_command_reads_fresh_text_without_manual_presync(tmp_path) -> None:
    target = tmp_path / "note.md"

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.workspace.active.path = target
            ed = app.query_one("#editor")
            ed.load_text("typed content")
            await pilot.pause()
            # cmd_save no longer pre-syncs; the auto-flush must still capture the
            # editor's text on disk.
            app.cmd_save()
            await pilot.pause()
            return target.read_text()

    assert _run(go()) == "typed content"


def test_switching_tabs_preserves_unsaved_edits(tmp_path) -> None:
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("A original")
    b.write_text("B original")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.workspace.open_path(a)
            app._load_active_into_editor()
            await pilot.pause()
            app.workspace.open_path(b)
            app._load_active_into_editor()
            await pilot.pause()

            ed = app.query_one("#editor")
            ed.load_text("B edited, not saved")
            await pilot.pause()

            # Switch back to A, then to B again — B's unsaved edit must survive
            # because switching flushes the outgoing editor into its Document.
            app.action_prev_tab()
            await pilot.pause()
            a_text = app.document.text
            app.action_next_tab()
            await pilot.pause()
            b_text = app.document.text
            return a_text, b_text

    a_text, b_text = _run(go())
    assert a_text == "A original"
    assert b_text == "B edited, not saved"


def test_loading_a_document_does_not_dirty_it() -> None:
    """Pushing text into the editor (load_active) is guarded, so the change event
    it triggers isn't recorded as a user edit."""

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            app.workspace.active.set_text("clean content")
            app.workspace.active.mark_saved()
            app._load_active_into_editor()
            await pilot.pause()
            return app.workspace.active.dirty

    assert _run(go()) is False

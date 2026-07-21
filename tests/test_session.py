"""Session persistence: the tabs you had open come back, ghosts don't."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from markstar.app import MarkStarApp
from markstar.domain.session import OpenFile, Session, from_toml, load, save, to_toml
from markstar.ui.welcome import WelcomeChoice


def _run(coro):
    return asyncio.run(coro)


# ---- pure serialisation -----------------------------------------------------


def test_round_trip(tmp_path: Path) -> None:
    s = Session(
        files=[OpenFile(tmp_path / "a.md", 12, 3), OpenFile(tmp_path / "b.md")],
        active=1,
        project_root=tmp_path,
    )
    back = from_toml(to_toml(s))
    assert back.files == s.files
    assert back.active == 1
    assert back.project_root == tmp_path


def test_paths_with_quotes_survive(tmp_path: Path) -> None:
    odd = tmp_path / 'a "quoted" name.md'
    back = from_toml(to_toml(Session(files=[OpenFile(odd)])))
    assert back.files[0].path == odd


def test_malformed_toml_yields_empty_session_not_an_exception() -> None:
    assert from_toml("this is not toml {{{").is_empty


def test_garbage_entries_are_skipped() -> None:
    toml = 'active = 0\n[[files]]\nline = 4\n'  # no path
    assert from_toml(toml).is_empty


def test_active_out_of_range_is_clamped(tmp_path: Path) -> None:
    toml = f'active = 99\n[[files]]\npath = "{tmp_path / "a.md"}"\n'
    assert from_toml(toml).active == 0


def test_existing_drops_missing_files_and_keeps_active(tmp_path: Path) -> None:
    real = tmp_path / "real.md"
    real.write_text("x", encoding="utf-8")
    s = Session(
        files=[OpenFile(tmp_path / "gone.md"), OpenFile(real)],
        active=1,
    )
    kept = s.existing()
    assert [f.path for f in kept.files] == [real]
    assert kept.active == 0  # followed the surviving file


def test_load_of_missing_file_is_empty(tmp_path: Path) -> None:
    assert load(tmp_path / "nope.toml").is_empty


def test_save_then_load(tmp_path: Path) -> None:
    p = tmp_path / "sub" / "session.toml"  # parent doesn't exist yet
    save(p, Session(files=[OpenFile(tmp_path / "a.md", 5, 2)]))
    assert load(p).files[0].line == 5


# ---- app integration --------------------------------------------------------


def test_quit_captures_open_tabs_and_splash_restores_them(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "cfg.toml"))
    monkeypatch.setenv("MARKSTAR_SESSION", str(tmp_path / "session.toml"))
    a, b = tmp_path / "one.md", tmp_path / "two.md"
    a.write_text("# One\n\nalpha\n", encoding="utf-8")
    b.write_text("# Two\n\nbeta\n", encoding="utf-8")

    async def quit_with_tabs():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app._open_doc(a)
            app._open_doc(b)
            await pilot.pause()
            with patch.object(app, "exit"):
                app.cmd_quit()
                for _ in range(6):
                    await pilot.pause()

    _run(quit_with_tabs())
    saved = load(tmp_path / "session.toml")
    assert [f.path for f in saved.files] == [a, b]

    async def relaunch_and_resume():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            with patch.object(
                app,
                "push_screen_wait",
                AsyncMock(return_value=WelcomeChoice("session")),
            ):
                await app._show_welcome()
            for _ in range(6):
                await pilot.pause()
            return [d.path for d in app.workspace.documents]

    assert _run(relaunch_and_resume()) == [a, b]


def test_restoring_skips_files_that_vanished(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "cfg.toml"))
    monkeypatch.setenv("MARKSTAR_SESSION", str(tmp_path / "session.toml"))
    real = tmp_path / "real.md"
    real.write_text("here", encoding="utf-8")
    save(
        tmp_path / "session.toml",
        Session(files=[OpenFile(tmp_path / "gone.md"), OpenFile(real)], active=0),
    )

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app._restore_session(load(tmp_path / "session.toml"))
            for _ in range(4):
                await pilot.pause()
            return [d.path for d in app.workspace.documents]

    assert _run(go()) == [real]


def test_untitled_buffers_are_not_recorded(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "cfg.toml"))
    monkeypatch.setenv("MARKSTAR_SESSION", str(tmp_path / "session.toml"))
    real = tmp_path / "real.md"
    real.write_text("x", encoding="utf-8")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app._open_doc(real)
            app.workspace.new_document(text="scratch")  # untitled
            await pilot.pause()
            app._capture_session()
            return load(tmp_path / "session.toml")

    saved = _run(go())
    assert [f.path for f in saved.files] == [real]  # nothing to reopen an untitled from


def test_caret_position_is_remembered_across_tabs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "cfg.toml"))
    monkeypatch.setenv("MARKSTAR_SESSION", str(tmp_path / "session.toml"))
    a = tmp_path / "a.md"
    a.write_text("\n".join(f"line {i}" for i in range(30)), encoding="utf-8")
    b = tmp_path / "b.md"
    b.write_text("short\n", encoding="utf-8")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app._open_doc(a)
            await pilot.pause()
            app.query_one("#editor").move_cursor((12, 4))
            await pilot.pause()
            app._open_doc(b)          # leaves a
            await pilot.pause()
            app.cmd_prev_tab()        # back to a
            for _ in range(4):
                await pilot.pause()
            return app.query_one("#editor").cursor_location

    assert _run(go()) == (12, 4)


def test_restore_disabled_by_preference(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MARKSTAR_CONFIG", str(tmp_path / "cfg.toml"))
    monkeypatch.setenv("MARKSTAR_SESSION", str(tmp_path / "session.toml"))
    real = tmp_path / "real.md"
    real.write_text("x", encoding="utf-8")

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.prefs.restore_session = False
            app._open_doc(real)
            app._capture_session()
            return (tmp_path / "session.toml").exists()

    assert _run(go()) is False

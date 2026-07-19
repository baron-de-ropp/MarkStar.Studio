"""StarBot chat panel: toggle, streaming into the transcript, unconfigured guard."""

from __future__ import annotations

import asyncio

from markstar.app import MarkStarApp
from markstar.ui.starbot_panel import StarBotPanel


def _run(coro):
    return asyncio.run(coro)


def _log_texts(app):
    # Render each transcript widget to plain text — assistant messages are Rich
    # renderables (Markdown), so str(render()) alone wouldn't expose their text.
    from rich.console import Console

    con = Console(width=80)
    out = []
    for c in app.query_one("#sb-log").children:
        with con.capture() as cap:
            con.print(c.render())
        out.append(cap.get())
    return out


class _StubChat:
    async def send(self, text, emit):
        emit(("tool", 'grep "sigil"'))
        emit(("text", "Two slips found."))
        emit(("done", None))


def test_sanitize_strips_emoji_keeps_arrows_and_escapes_brackets() -> None:
    from markstar.ui.starbot_panel import _sanitize

    assert "🗺" not in _sanitize("map 🗺️ here")
    assert _sanitize("a → b") == "a → b"        # arrows are single-cell, kept
    assert _sanitize("[x]") == "\\[x]"          # markup bracket escaped


def test_ctrl_k_toggles_panel() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = app.query_one("#starbot-panel", StarBotPanel)
            before = panel.is_open
            app.cmd_toggle_starbot()
            await pilot.pause()
            opened = panel.is_open
            app.cmd_toggle_starbot()
            await pilot.pause()
            return before, opened, panel.is_open

    before, opened, closed = _run(go())
    assert before is False and opened is True and closed is False


def test_submit_streams_reply_into_transcript() -> None:
    async def go():
        app = MarkStarApp()
        async with app.run_test(size=(160, 24)) as pilot:
            await pilot.pause()
            app._starbot_chat = _StubChat()
            app.cmd_toggle_starbot()
            await pilot.pause()
            app._on_starbot_submit(StarBotPanel.Submitted("check sigils"))
            for _ in range(6):
                await pilot.pause()
            return _log_texts(app)

    texts = _run(go())
    joined = "\n".join(texts)
    assert "You" in joined
    assert 'grep "sigil"' in joined     # tool-activity line
    # The assistant reply is rendered as Markdown (a Rich renderable that doesn't
    # read back as plain text here); its presence is a third transcript widget.
    assert len(texts) == 3


class _StubClient:
    async def stream(self, messages, tools=None):
        yield ("text", "hi there")


def test_turn_persists_transcript_and_new_chat_resets(tmp_path) -> None:
    from markstar.ai.chat import StarBotChat
    from markstar.ai.history import ChatStore

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app._project_root = lambda: tmp_path  # save history under tmp
            app._starbot_chat = StarBotChat(_StubClient(), tools=None)
            app.cmd_toggle_starbot()
            await pilot.pause()
            app._on_starbot_submit(StarBotPanel.Submitted("hello"))
            for _ in range(6):
                await pilot.pause()
            had = app._starbot_transcript is not None
            app.cmd_starbot_new_chat()
            await pilot.pause()
            return had, app._starbot_transcript, app._starbot_chat

    had, transcript_after, chat_after = _run(go())
    saved = ChatStore(tmp_path).list()
    assert had is True
    assert len(saved) == 1
    assert any(
        m.get("role") == "user" and m.get("content") == "hello"
        for m in saved[0].messages
    )
    # New chat cleared the session state (the saved file stays on disk).
    assert transcript_after is None and chat_after is None


def test_unconfigured_guides_user_to_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STARBOT_CONFIG", str(tmp_path / "none.toml"))

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.cmd_toggle_starbot()
            await pilot.pause()
            app._on_starbot_submit(StarBotPanel.Submitted("hi"))
            await pilot.pause()
            return _log_texts(app)

    texts = _run(go())
    assert any("StarBot…" in t or "no connection" in t for t in texts)

"""ChatStore / ChatTranscript: per-project transcript persistence."""

from __future__ import annotations

from markstar.ai.history import DIRNAME, ChatStore, ChatTranscript


def _msgs(user_text):
    return [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": "sure"},
    ]


def test_save_and_load_round_trip(tmp_path) -> None:
    store = ChatStore(tmp_path)
    t = ChatTranscript("2026-07-19T10-00-00", "2026-07-19T10:00:00", _msgs("hello"))
    store.save(t)
    assert (tmp_path / DIRNAME / "2026-07-19T10-00-00.json").exists()
    loaded = store.load("2026-07-19T10-00-00")
    assert loaded is not None
    assert loaded.messages == t.messages
    assert loaded.created == t.created


def test_title_and_turn_count() -> None:
    t = ChatTranscript("id", "", _msgs("check chapter three please"))
    assert t.title == "check chapter three please"
    assert t.turn_count == 1
    assert ChatTranscript("id", "", []).title == "(empty)"


def test_long_title_is_truncated() -> None:
    long = "x" * 100
    assert ChatTranscript("id", "", _msgs(long)).title.endswith("…")


def test_list_is_newest_first(tmp_path) -> None:
    store = ChatStore(tmp_path)
    store.save(ChatTranscript("a", "2026-01-01T00:00:00", _msgs("old")))
    store.save(ChatTranscript("b", "2026-06-01T00:00:00", _msgs("new")))
    ids = [t.id for t in store.list()]
    assert ids == ["b", "a"]


def test_list_skips_malformed_files(tmp_path) -> None:
    store = ChatStore(tmp_path)
    store.save(ChatTranscript("ok", "2026-01-01T00:00:00", _msgs("fine")))
    (tmp_path / DIRNAME / "broken.json").write_text("{not json")
    assert [t.id for t in store.list()] == ["ok"]


def test_delete_removes_transcript(tmp_path) -> None:
    store = ChatStore(tmp_path)
    store.save(ChatTranscript("gone", "2026-01-01T00:00:00", _msgs("bye")))
    store.delete("gone")
    assert store.load("gone") is None
    assert store.list() == []


def test_load_missing_returns_none(tmp_path) -> None:
    assert ChatStore(tmp_path).load("nope") is None


def test_history_picker_delete_removes_transcript(tmp_path) -> None:
    import asyncio

    from markstar.app import MarkStarApp
    from markstar.ui.starbot_history_screen import ChatHistoryScreen

    store = ChatStore(tmp_path)
    store.save(ChatTranscript("a", "2026-01-01T00:00:00", _msgs("first")))
    store.save(ChatTranscript("b", "2026-02-01T00:00:00", _msgs("second")))

    async def go():
        app = MarkStarApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            scr = ChatHistoryScreen(store.list(), on_delete=store.delete)
            await app.push_screen(scr)
            await pilot.pause()
            ol = scr.query_one("#hist-list")
            ol.highlighted = 0  # newest = "b"
            scr.action_delete()
            await pilot.pause()

    asyncio.run(go())
    remaining = [t.id for t in store.list()]
    assert remaining == ["a"]  # "b" was deleted from disk

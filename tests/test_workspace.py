"""Unit tests for Workspace (multi-tab)."""

from __future__ import annotations

from pathlib import Path

import pytest

from markstar.domain.document import Document
from markstar.domain.workspace import Workspace


def test_starts_with_one_empty_document() -> None:
    ws = Workspace()
    assert ws.count == 1
    assert ws.active_index == 0
    assert ws.active.text == ""
    assert ws.active.path is None


def test_new_document_appends_and_focuses() -> None:
    ws = Workspace()
    first = ws.active
    second = ws.new_document(text="hello")
    assert ws.count == 2
    assert ws.active is second
    assert ws.active.text == "hello"
    assert ws.documents[0] is first


def test_next_and_prev_wrap() -> None:
    ws = Workspace()
    ws.new_document(text="a")
    ws.new_document(text="b")
    assert ws.active.text == "b"
    ws.prev_tab()
    assert ws.active.text == "a"
    ws.prev_tab()
    assert ws.active.text == ""  # original empty
    ws.next_tab()
    assert ws.active.text == "a"
    ws.next_tab()
    assert ws.active.text == "b"
    ws.next_tab()
    assert ws.active.text == ""


def test_open_path_reuses_tab(tmp_path: Path) -> None:
    path = tmp_path / "ch.md"
    path.write_text("body", encoding="utf-8")
    ws = Workspace()
    d1 = ws.open_path(path)
    assert d1.text == "body"
    ws.new_document(text="other")
    d2 = ws.open_path(path)
    assert ws.count == 2
    assert d2 is d1
    assert ws.active is d1


def test_close_active_leaves_neighbor() -> None:
    ws = Workspace()
    ws.new_document(text="keep")
    ws.new_document(text="close me")
    assert ws.active.text == "close me"
    ws.close_active()
    assert ws.count == 2
    assert ws.active.text == "keep"


def test_close_last_resets_empty() -> None:
    ws = Workspace()
    ws.active.insert(0, "gone")
    ws.close_active()
    assert ws.count == 1
    assert ws.active.text == ""
    assert ws.active.dirty is False


def test_close_all() -> None:
    ws = Workspace()
    ws.new_document(text="a")
    ws.new_document(text="b")
    ws.close_all()
    assert ws.count == 1
    assert ws.active.text == ""


def test_close_others_keeps_active() -> None:
    ws = Workspace()
    # indices: 0="", 1="a", 2="keep", 3="c"
    ws.new_document(text="a")
    ws.new_document(text="keep")
    ws.new_document(text="c")
    ws.set_active(2)
    assert ws.active.text == "keep"
    ws.close_others()
    assert ws.count == 1
    assert ws.active.text == "keep"
    assert ws.active_index == 0


def test_set_active_bounds() -> None:
    ws = Workspace()
    ws.new_document()
    with pytest.raises(IndexError):
        ws.set_active(5)


def test_has_dirty() -> None:
    ws = Workspace()
    assert ws.has_dirty is False
    ws.active.insert(0, "x")
    assert ws.has_dirty is True
    assert len(ws.dirty_documents()) == 1
    ws.new_document()
    assert len(ws.dirty_documents()) == 1
    ws.active.insert(0, "y")
    assert len(ws.dirty_documents()) == 2

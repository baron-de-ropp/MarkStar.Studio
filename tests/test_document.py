"""Unit tests for the Document domain model (P0)."""

from __future__ import annotations

from pathlib import Path

import pytest

from prose.domain.document import Document


def test_new_document_is_empty_and_clean() -> None:
    doc = Document()
    assert doc.text == ""
    assert doc.path is None
    assert doc.dirty is False
    assert doc.can_undo is False
    assert doc.can_redo is False
    assert doc.word_count() == 0


def test_insert_text_makes_dirty_and_updates_content() -> None:
    doc = Document()
    doc.insert(0, "Hello world")
    assert doc.text == "Hello world"
    assert doc.dirty is True
    assert doc.word_count() == 2


def test_insert_in_middle() -> None:
    doc = Document()
    doc.insert(0, "Hello world")
    doc.insert(5, " beautiful")
    assert doc.text == "Hello beautiful world"


def test_delete_range() -> None:
    doc = Document()
    doc.insert(0, "Hello world")
    doc.delete(5, 11)  # remove " world"
    assert doc.text == "Hello"


def test_replace_range() -> None:
    doc = Document()
    doc.insert(0, "Hello world")
    doc.replace(6, 11, "prose")
    assert doc.text == "Hello prose"


def test_undo_insert() -> None:
    doc = Document()
    doc.insert(0, "abc")
    assert doc.can_undo is True
    doc.undo()
    assert doc.text == ""
    assert doc.can_undo is False
    assert doc.can_redo is True


def test_redo_after_undo() -> None:
    doc = Document()
    doc.insert(0, "abc")
    doc.undo()
    doc.redo()
    assert doc.text == "abc"
    assert doc.can_redo is False


def test_edit_after_undo_clears_redo() -> None:
    doc = Document()
    doc.insert(0, "one")
    doc.insert(3, " two")
    doc.undo()  # back to "one"
    assert doc.can_redo is True
    doc.insert(3, " three")
    assert doc.text == "one three"
    assert doc.can_redo is False


def test_multiple_undos() -> None:
    doc = Document()
    doc.insert(0, "a")
    doc.insert(1, "b")
    doc.insert(2, "c")
    doc.undo()
    doc.undo()
    doc.undo()
    assert doc.text == ""
    doc.redo()
    doc.redo()
    assert doc.text == "ab"


def test_word_count_ignores_extra_whitespace() -> None:
    doc = Document()
    doc.insert(0, "  hello   world\n\nfoo  ")
    assert doc.word_count() == 3


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "chapter.md"
    doc = Document()
    doc.insert(0, "# Title\n\nHello **world**.\n")
    doc.save(path)
    assert path.read_text(encoding="utf-8") == "# Title\n\nHello **world**.\n"
    assert doc.dirty is False
    assert doc.path == path

    loaded = Document.load(path)
    assert loaded.text == doc.text
    assert loaded.path == path
    assert loaded.dirty is False


def test_save_without_path_raises() -> None:
    doc = Document()
    doc.insert(0, "x")
    with pytest.raises(ValueError, match="path"):
        doc.save()


def test_mark_saved_clears_dirty() -> None:
    doc = Document()
    doc.insert(0, "x")
    assert doc.dirty is True
    doc.mark_saved()
    assert doc.dirty is False


def test_set_text_records_undo() -> None:
    doc = Document()
    doc.insert(0, "old")
    doc.set_text("new entire buffer")
    assert doc.text == "new entire buffer"
    doc.undo()
    assert doc.text == "old"

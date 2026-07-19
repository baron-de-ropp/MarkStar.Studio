"""Unit tests for find / replace."""

from __future__ import annotations

from markstar.domain.document import Document
from markstar.domain.search import (
    find_all,
    find_next,
    find_prev,
    replace_all,
    replace_match,
    step_find,
)


def test_find_next_basic() -> None:
    text = "the cat sat on the mat"
    m = find_next(text, "the")
    assert m is not None
    assert (m.start, m.end) == (0, 3)
    m2 = find_next(text, "the", start=1)
    assert m2 is not None
    assert m2.start == 15


def test_find_next_wraps() -> None:
    text = "one two one"
    m = find_next(text, "one", start=9)  # past second "one"
    assert m is not None
    assert m.start == 0


def test_find_prev() -> None:
    text = "one two one"
    m = find_prev(text, "one", start=10)
    assert m is not None
    assert m.start == 8
    m2 = find_prev(text, "one", start=8)
    assert m2 is not None
    assert m2.start == 0


def test_step_find_next_and_prev_cycle() -> None:
    text = "aa x aa y aa"
    # starts: 0, 5, 10
    first = step_find(text, "aa", direction="next", cursor=0, current_start=None)
    assert first is not None and first.start == 0
    second = step_find(text, "aa", direction="next", current_start=0)
    assert second is not None and second.start == 5
    third = step_find(text, "aa", direction="next", current_start=5)
    assert third is not None and third.start == 10
    wrap = step_find(text, "aa", direction="next", current_start=10)
    assert wrap is not None and wrap.start == 0

    back = step_find(text, "aa", direction="prev", current_start=5)
    assert back is not None and back.start == 0
    back_wrap = step_find(text, "aa", direction="prev", current_start=0)
    assert back_wrap is not None and back_wrap.start == 10


def test_find_case_insensitive() -> None:
    text = "Hello HELLO"
    m = find_next(text, "hello")
    assert m is not None
    assert m.start == 0
    m2 = find_next(text, "hello", start=1)
    assert m2 is not None
    assert m2.start == 6


def test_find_all() -> None:
    matches = find_all("aaa", "aa")
    assert len(matches) == 1  # non-overlapping from left
    assert matches[0].start == 0


def test_replace_all() -> None:
    doc = Document()
    doc.insert(0, "foo bar foo")
    n = replace_all(doc, "foo", "baz")
    assert n == 2
    assert doc.text == "baz bar baz"
    doc.undo()
    assert doc.text == "foo bar foo"


def test_replace_match() -> None:
    doc = Document()
    doc.insert(0, "hello world")
    m = find_next(doc.text, "world")
    assert m is not None
    new_m = replace_match(doc, m, "prose")
    assert doc.text == "hello prose"
    assert new_m.start == 6
    assert new_m.end == 11


def test_empty_query() -> None:
    assert find_next("abc", "") is None
    assert find_all("abc", "") == []
    doc = Document()
    doc.insert(0, "abc")
    assert replace_all(doc, "", "x") == 0

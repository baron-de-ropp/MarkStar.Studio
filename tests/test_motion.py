"""Unit tests for motion helpers."""

from __future__ import annotations

from markstar.domain.motion import paragraph_down, paragraph_up, word_left, word_right


def test_word_right_and_left() -> None:
    text = "hello world"
    assert word_right(text, 0) == 6  # after hello + space → start of world? 
    # word_right from start of hello should go to start of world
    assert word_right(text, 0) == 6
    assert word_left(text, 6) == 0
    assert word_left(text, 8) == 6  # mid "world" → start of world


def test_word_right_at_end() -> None:
    text = "ab"
    assert word_right(text, 2) == 2


def test_paragraph_navigation() -> None:
    text = "para one\n\nstill two\n\nthree"
    # index in first para
    assert paragraph_up(text, 3) == 0
    assert paragraph_down(text, 0) == 10  # after \n\n following "para one"
    assert paragraph_down(text, 10) == 21
    assert paragraph_up(text, 15) == 10

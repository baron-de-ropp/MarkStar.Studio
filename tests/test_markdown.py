"""Pure Markdown logic — spans, word bounds, and the emphasis-toggle math.

These need no UI: they're plain string functions extracted from app.py so the
editing math can be exercised directly (it used to require a mounted editor).
"""

from __future__ import annotations

from markstar.domain.markdown import (
    RE_BOLD,
    RE_CODE,
    RE_ITALIC,
    markdown_spans,
    toggle_emphasis,
    word_bounds,
)


def test_word_bounds_expands_to_surrounding_word() -> None:
    line = "the quick brown"
    assert word_bounds(line, 6) == (4, 9)  # inside "quick"
    assert word_bounds(line, 4) == (4, 9)  # at its start
    assert word_bounds(line, 9) == (4, 9)  # at its end


def test_word_bounds_adjacent_word_is_grabbed_leftward() -> None:
    # At col 1 (just past "a"), the bound expands left into that word.
    assert word_bounds("a b", 1) == (0, 1)


def test_word_bounds_in_pure_whitespace_is_empty() -> None:
    assert word_bounds("a  b", 2) == (2, 2)  # between the two spaces


def test_word_bounds_clamps_out_of_range() -> None:
    # Clamped to the ends, then expands into the touching word.
    assert word_bounds("abc", 99) == (0, 3)
    assert word_bounds("abc", -5) == (0, 3)


def test_markdown_spans_bold() -> None:
    spans = markdown_spans("a **bold** c")
    assert (2, 4, "marker") in spans
    assert (4, 8, "strong") in spans
    assert (8, 10, "marker") in spans


def test_markdown_spans_heading_and_quote() -> None:
    assert (0, 3, "marker") in markdown_spans("## Title")
    assert (3, 8, "heading") in markdown_spans("## Title")
    assert markdown_spans("> hi")[0] == (0, 2, "marker")


def test_toggle_emphasis_wraps_plain_word() -> None:
    # word "bold" occupies cols 0..4; caret at end.
    new, caret = toggle_emphasis("bold", "**", RE_BOLD, 0, 4, 4)
    assert new == "**bold**"
    assert caret == 6  # caret was inside the word → shifts past opening marker


def test_toggle_emphasis_strips_when_already_bold() -> None:
    line = "**bold**"
    new, caret = toggle_emphasis(line, "**", RE_BOLD, 2, 6, 4)
    assert new == "bold"
    assert caret == 2  # inside the emphasized run → shifts back by one marker


def test_toggle_emphasis_roundtrip_is_identity() -> None:
    line, marker, rx = "word", "*", RE_ITALIC
    wrapped, _ = toggle_emphasis(line, marker, rx, 0, 4, 2)
    assert wrapped == "*word*"
    back, _ = toggle_emphasis(wrapped, marker, rx, 1, 5, 3)
    assert back == "word"


def test_toggle_emphasis_bare_caret_inserts_empty_markers() -> None:
    new, caret = toggle_emphasis("", "`", RE_CODE, 0, 0, 0)
    assert new == "``"
    # caret <= range start → stays at 0 (before the markers). Multi-line/empty
    # toggles go through _wrap_selection in the UI, which parks between them.
    assert caret == 0

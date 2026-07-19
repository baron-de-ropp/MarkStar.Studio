"""Caret motion helpers for creature-comfort navigation (pure functions)."""

from __future__ import annotations


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch in "_'"


def word_left(text: str, index: int) -> int:
    """Move to the start of the previous or current word."""
    index = max(0, min(index, len(text)))
    if index == 0:
        return 0
    i = index - 1
    while i > 0 and not _is_word_char(text[i]):
        i -= 1
    while i > 0 and _is_word_char(text[i - 1]):
        i -= 1
    return i


def word_right(text: str, index: int) -> int:
    """Move to the start of the next word (or end of text)."""
    index = max(0, min(index, len(text)))
    n = len(text)
    if index >= n:
        return n
    i = index
    if _is_word_char(text[i]):
        while i < n and _is_word_char(text[i]):
            i += 1
    while i < n and not _is_word_char(text[i]):
        i += 1
    return i


def paragraph_up(text: str, index: int) -> int:
    """Start of current or previous paragraph (blank-line separated)."""
    index = max(0, min(index, len(text)))
    start = text.rfind("\n\n", 0, index)
    para_start = 0 if start == -1 else start + 2
    if index > para_start:
        return para_start
    if para_start == 0:
        return 0
    prev = text.rfind("\n\n", 0, max(0, para_start - 1))
    return 0 if prev == -1 else prev + 2


def paragraph_down(text: str, index: int) -> int:
    """Start of next paragraph, or end of text."""
    index = max(0, min(index, len(text)))
    nxt = text.find("\n\n", index)
    if nxt == -1:
        return len(text)
    return min(len(text), nxt + 2)
